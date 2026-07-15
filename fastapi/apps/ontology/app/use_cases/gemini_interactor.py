from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from ontology.app.dtos.gemini_generation_dto import GeminiGenerationCommand
from ontology.app.ports.input.gemini_generation_use_case import (
    GeminiGenerationUseCase,
)
from ontology.app.ports.output.gemini_generation_port import GeminiGenerationPort

logger = logging.getLogger("uvicorn.error")


class GeminiInteractor(GeminiGenerationUseCase):
    def __init__(self, generator: GeminiGenerationPort) -> None:
        self._generator = generator

    async def stream_generate(
        self, command: GeminiGenerationCommand
    ) -> AsyncIterator[str]:
        logger.info(
            "[ontology.gemini_generation] 허브 진입 | prompt_len=%d",
            len(command.prompt),
        )
        chunk_count = 0
        async for chunk in self._generator.stream_generate(command):
            chunk_count += 1
            yield chunk
        logger.info("[ontology.gemini_generation] 허브 완료 | chunks=%d", chunk_count)
