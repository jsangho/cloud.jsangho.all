from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.matrix.vault_keymaker_secret_manager import get_keymaker
from kayfabe.adapter.outbound.orm.wrestler_orm import WrestlerOrm
from kayfabe.app.dtos.wrestler_chat_dto import WrestlerChatCommand, WrestlerChatTurnDto
from kayfabe.app.ports.output.wrestler_chat_port import WrestlerChatPort
from ontology.app.dtos.exaone_generation_dto import ExaoneGenerationCommand
from ontology.app.ports.input.exaone_generation_use_case import (
    ExaoneGenerationUseCase,
)

logger = logging.getLogger("uvicorn.error")

GORILLA_PERSONA = (
    "당신은 WWE 백스테이지 '고릴라 포지션'을 지키는 베테랑 프로듀서입니다. "
    "선수들이 입장하기 직전 대기하는 그 자리에서, 로스터의 모든 정보를 꿰고 있습니다. "
    "아래 [선수 정보]에 있는 사실만 근거로, 한국어로 3~5문장 안에 간결하고 확신 있게 답하세요. "
    "[선수 정보]에 없는 내용은 추측하지 말고 모른다고 답하세요."
)
TOP_K = 5
MAX_PROMPT_MESSAGES = 8


class WrestlerChatRepository(WrestlerChatPort):
    """kayfabe(스포크)의 RAG 리포지토리.

    검색(임베딩 유사도)과 프롬프트 구성은 kayfabe가 직접 소유하고, 실제 텍스트
    생성은 ontology(허브)의 ExaoneGenerationUseCase에 위임한다 — 스포크 ↔ 스포크
    직접 의존을 만들지 않기 위해 생성 능력은 허브를 경유한다.
    """

    def __init__(
        self, session: AsyncSession, generation_use_case: ExaoneGenerationUseCase
    ) -> None:
        self.session = session
        self._generation_use_case = generation_use_case

    async def stream_chat(self, command: WrestlerChatCommand) -> AsyncIterator[str]:
        user_messages = [m for m in command.messages if m.role == "user"]
        if not user_messages:
            yield "궁금한 선수 이름이나 정보를 물어봐 주세요."
            return

        question = user_messages[-1].text
        logger.info("[kayfabe.wrestler_chat] 질문 수신 | question=%r", question)

        context = await self._retrieve_context(question)
        prompt = self._build_prompt(command.messages, context)

        logger.info(
            "[kayfabe.wrestler_chat] ontology 허브로 위임 | prompt_len=%d", len(prompt)
        )
        chunk_count = 0
        async for chunk in self._generation_use_case.stream_generate(
            ExaoneGenerationCommand(prompt=prompt)
        ):
            chunk_count += 1
            yield chunk
        logger.info(
            "[kayfabe.wrestler_chat] 답변 스트리밍 완료 | chunks=%d", chunk_count
        )

    async def _retrieve_context(self, question: str) -> str:
        query_embedding = await asyncio.to_thread(get_keymaker().embed_text, question)
        stmt = (
            select(WrestlerOrm)
            .where(WrestlerOrm.embedding.is_not(None))
            .order_by(WrestlerOrm.embedding.op("<=>")(query_embedding))
            .limit(TOP_K)
        )
        wrestlers = (await self.session.scalars(stmt)).all()
        logger.info(
            "[kayfabe.wrestler_chat] RAG 검색 완료 | top_k=%d | 결과=%s",
            TOP_K,
            [w.name for w in wrestlers],
        )
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
