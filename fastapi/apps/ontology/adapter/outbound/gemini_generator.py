from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator

from core.matrix.vault_keymaker_secret_manager import (
    DEFAULT_GEMINI_MODEL_ID,
    get_keymaker,
)
from google import genai

from ontology.app.dtos.gemini_generation_dto import GeminiGenerationCommand
from ontology.app.ports.output.gemini_generation_port import GeminiGenerationPort

logger = logging.getLogger("uvicorn.error")


def _default_model() -> str:
    """`GEMINI_MODEL`이 있으면 그것, 없으면 core의 기본값.

    모델 ID를 코드 상수로 박아 두면 모델이 은퇴할 때마다 커밋·배포가 필요하다.
    환경변수로 두면 `.env` 한 줄과 재기동으로 끝난다.
    """
    return (os.getenv("GEMINI_MODEL") or "").strip() or DEFAULT_GEMINI_MODEL_ID


class GeminiGenerator(GeminiGenerationPort):
    """Google Gemini API(GEMINI_API_KEY)로 텍스트를 스트리밍 생성하는 어댑터."""

    def __init__(self) -> None:
        self._client = genai.Client(api_key=get_keymaker().get_gemini_api_key())

    async def stream_generate(
        self, command: GeminiGenerationCommand
    ) -> AsyncIterator[str]:
        model = command.model or _default_model()
        logger.info("[ontology.gemini_generator] Gemini 호출 시작 | model=%s", model)
        stream = await self._client.aio.models.generate_content_stream(
            model=model, contents=command.prompt
        )
        async for chunk in stream:
            if chunk.text:
                yield chunk.text
        logger.info("[ontology.gemini_generator] Gemini 호출 종료 | model=%s", model)
