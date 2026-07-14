from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.matrix.vault_keymaker_secret_manager import get_keymaker
from kayfabe.adapter.outbound.orm.wrestler_orm import WrestlerOrm
from kayfabe.app.dtos.wrestler_chat_dto import WrestlerChatCommand, WrestlerChatTurnDto
from kayfabe.app.ports.output.wrestler_chat_port import WrestlerChatPort

GORILLA_PERSONA = (
    "당신은 WWE 백스테이지 '고릴라 포지션'을 지키는 베테랑 프로듀서입니다. "
    "선수들이 입장하기 직전 대기하는 그 자리에서, 로스터의 모든 정보를 꿰고 있습니다. "
    "아래 [선수 정보]에 있는 사실만 근거로, 한국어로 3~5문장 안에 간결하고 확신 있게 답하세요. "
    "[선수 정보]에 없는 내용은 추측하지 말고 모른다고 답하세요."
)
TOP_K = 5
MAX_PROMPT_MESSAGES = 8


class WrestlerChatRepository(WrestlerChatPort):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def stream_chat(self, command: WrestlerChatCommand) -> AsyncIterator[str]:
        user_messages = [m for m in command.messages if m.role == "user"]
        if not user_messages:
            yield "궁금한 선수 이름이나 정보를 물어봐 주세요."
            return

        question = user_messages[-1].text
        context = await self._retrieve_context(question)
        prompt = self._build_prompt(command.messages, context)
        async for chunk in self._stream_gemini(prompt):
            yield chunk

    async def _retrieve_context(self, question: str) -> str:
        query_embedding = await asyncio.to_thread(get_keymaker().embed_text, question)
        stmt = (
            select(WrestlerOrm)
            .where(WrestlerOrm.embedding.is_not(None))
            .order_by(WrestlerOrm.embedding.op("<=>")(query_embedding))
            .limit(TOP_K)
        )
        wrestlers = (await self.session.scalars(stmt)).all()
        if not wrestlers:
            return "(일치하는 선수 정보 없음)"
        return "\n".join(self._describe(w) for w in wrestlers)

    def _describe(self, w: WrestlerOrm) -> str:
        fields = [
            ("이름", w.name),
            ("본명", w.real_name),
            ("링네임", w.ring_names),
            ("신장", w.height),
            ("체중", w.weight),
            ("출신", w.birth_place),
            ("연고지", w.billed_from),
            ("트레이너", w.trainer),
            ("데뷔", w.debut),
            ("은퇴", w.retired),
            ("피니셔", w.finisher),
        ]
        parts = [f"{label}: {value}" for label, value in fields if value]
        return "- " + " / ".join(parts)

    def _build_prompt(
        self, messages: tuple[WrestlerChatTurnDto, ...], context: str
    ) -> str:
        recent = messages[-MAX_PROMPT_MESSAGES:]
        lines = [
            f"{'질문자' if turn.role == 'user' else '고릴라 포지션'}: {turn.text.strip()}"
            for turn in recent
        ]
        return (
            f"{GORILLA_PERSONA}\n\n"
            f"[선수 정보]\n{context}\n\n" + "\n".join(lines) + "\n고릴라 포지션:"
        )

    async def _stream_gemini(self, prompt: str) -> AsyncIterator[str]:
        model = self._require_gemini_model()
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[str | None] = asyncio.Queue()
        _ERROR_PREFIX = "__WRESTLER_CHAT_ERROR__"

        def _produce() -> None:
            try:
                response = model.generate_content(prompt, stream=True)
                for chunk in response:
                    text = getattr(chunk, "text", None) or ""
                    if text:
                        loop.call_soon_threadsafe(queue.put_nowait, text)
            except Exception as e:  # noqa: BLE001
                loop.call_soon_threadsafe(queue.put_nowait, f"{_ERROR_PREFIX}{e}")
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)

        loop.run_in_executor(None, _produce)

        while True:
            item = await queue.get()
            if item is None:
                break
            if item.startswith(_ERROR_PREFIX):
                raise self._to_http_exception(item[len(_ERROR_PREFIX) :])
            yield item

    def _require_gemini_model(self):
        keymaker = get_keymaker()
        if not keymaker.is_gemini_ready():
            raise HTTPException(
                status_code=503,
                detail="GEMINI_API_KEY가 설정되지 않았습니다. .env 에 키를 넣어 주세요.",
            )
        return keymaker.get_gemini_model()

    def _to_http_exception(self, err: str) -> HTTPException:
        if "429" in err or "quota" in err.lower() or "ResourceExhausted" in err:
            return HTTPException(
                status_code=429,
                detail="Gemini API 할당량을 초과했습니다. 잠시 후 다시 시도해주세요.",
            )
        return HTTPException(status_code=502, detail=f"Gemini 호출 실패: {err}")
