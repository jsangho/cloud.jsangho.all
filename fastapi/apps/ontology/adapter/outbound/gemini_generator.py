from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from core.matrix.vault_keymaker_secret_manager import get_keymaker
from google import genai

from ontology.app.dtos.gemini_generation_dto import GeminiGenerationCommand
from ontology.app.ports.output.gemini_generation_port import GeminiGenerationPort

logger = logging.getLogger("uvicorn.error")

_MODEL_ID = "gemini-3.5-flash"


class GeminiGenerator(GeminiGenerationPort):
    """Google Gemini API(GEMINI_API_KEY)로 텍스트를 스트리밍 생성하는 어댑터."""

    def __init__(self) -> None:
        self._client = genai.Client(api_key=get_keymaker().get_gemini_api_key())

    async def stream_generate(
        self, command: GeminiGenerationCommand
    ) -> AsyncIterator[str]:
        logger.info(
            "[ontology.gemini_generator] Gemini 호출 시작 | model=%s", _MODEL_ID
        )
        stream = await self._client.aio.models.generate_content_stream(
            model=_MODEL_ID, contents=command.prompt
        )
        async for chunk in stream:
            if chunk.text:
                yield chunk.text
        logger.info(
            "[ontology.gemini_generator] Gemini 호출 종료 | model=%s", _MODEL_ID
        )
