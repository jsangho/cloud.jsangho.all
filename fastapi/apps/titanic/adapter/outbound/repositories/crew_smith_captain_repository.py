from __future__ import annotations

from collections.abc import Iterator

from core.matrix.vault_keymaker_secret_manager import Keymaker
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import HTTPException
from titanic.app.dtos.crew_smith_captain_dto import (
    ChatResponse,
    SmithCaptainChatCommand,
    SmithCaptainChatTurnDto,
    SmithCaptainQuery,
    SmithCaptainResponse,
)
from titanic.app.ports.output.crew_smith_captain_port import SmithCaptainPort

SMITH_PERSONA = (
    "당신은 RMS 타이타닉의 에드워드 스미스 선장입니다. "
    "1912년 어조로 한국어로 2~4문장 안에 간결히 답하세요."
)
MAX_PROMPT_MESSAGES = 8


class SmithCaptainRepository(SmithCaptainPort):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def introduce_myself(self, query: SmithCaptainQuery) -> SmithCaptainResponse:
        return SmithCaptainResponse(
            id=query.id * 10000,
            name=query.name + "가 레포지토리에 다녀옴",
        )

    async def chat(self, command: SmithCaptainChatCommand) -> SmithCaptainResponse:
        prompt = self._build_prompt(command.messages)
        reply = self._generate_reply(prompt)
        return ChatResponse(reply=reply)

    def chat_stream(self, command: SmithCaptainChatCommand) -> Iterator[str]:
        prompt = self._build_prompt(command.messages)
        model = self._require_gemini_model()
        try:
            response = model.generate_content(prompt, stream=True)
            for chunk in response:
                text = getattr(chunk, "text", None) or ""
                if text:
                    yield text
        except Exception as e:
            raise self._to_http_exception(e) from e

    def _build_prompt(self, messages: tuple[SmithCaptainChatTurnDto, ...]) -> str:
        recent = messages[-MAX_PROMPT_MESSAGES:]
        lines: list[str] = []
        for turn in recent:
            label = "승객" if turn.role == "user" else "선장"
            lines.append(f"{label}: {turn.text.strip()}")
        return f"{SMITH_PERSONA}\n\n" + "\n".join(lines) + "\n선장:"

    def _generate_reply(self, prompt: str) -> str:
        model = self._require_gemini_model()
        try:
            response = model.generate_content(prompt)
        except Exception as e:
            raise self._to_http_exception(e) from e

        try:
            text = (response.text or "").strip()
        except ValueError as e:
            feedback = getattr(response, "prompt_feedback", None)
            raise HTTPException(
                status_code=400,
                detail=f"응답 텍스트를 읽을 수 없습니다: {e!s}. prompt_feedback={feedback}",
            ) from e

        if not text:
            reason = None
            if getattr(response, "candidates", None):
                c0 = response.candidates[0]
                reason = getattr(c0, "finish_reason", None)
            raise HTTPException(
                status_code=502,
                detail=(
                    "모델이 비어 있는 응답을 반환했습니다."
                    + (f" (finish_reason={reason})" if reason else "")
                ),
            )
        return text

    def _require_gemini_model(self):
        keymaker = Keymaker.instance()
        if not keymaker.is_gemini_ready():
            if not keymaker.get_gemini_api_key():
                raise HTTPException(
                    status_code=503,
                    detail="GEMINI_API_KEY가 설정되지 않았습니다. sangho/.env 에 키를 넣어 주세요.",
                )
            raise HTTPException(
                status_code=503,
                detail=(
                    "Gemini 패키지가 설치되지 않았습니다. "
                    "sangho 폴더에서 `pip install -r requirements.txt` 후 서버를 재시작하세요."
                ),
            )
        return keymaker.get_gemini_model()

    def _to_http_exception(self, error: Exception) -> HTTPException:
        err = str(error)
        if (
            "429" in err
            or "quota" in err.lower()
            or "ResourceExhausted" in type(error).__name__
        ):
            return HTTPException(
                status_code=429,
                detail=(
                    "Gemini API 무료 할당량을 초과했거나, 이 프로젝트에 무료 할당량이 "
                    "활성화되지 않았습니다(limit: 0). "
                    "1~2분 후 다시 시도하거나, "
                    "https://aistudio.google.com/apikey 에서 새 키를 발급하고 "
                    "https://ai.dev/rate-limit 에서 사용량을 확인하세요. "
                    "계속되면 Google AI Studio에서 결제(빌링) 연결 후 무료 한도가 켜집니다."
                ),
            )
        return HTTPException(status_code=502, detail=f"Gemini 호출 실패: {error!s}")
