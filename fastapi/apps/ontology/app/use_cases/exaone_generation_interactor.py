from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from ontology.app.dtos.exaone_generation_dto import ExaoneGenerationCommand
from ontology.app.ports.input.exaone_generation_use_case import (
    ExaoneGenerationUseCase,
)
from ontology.app.ports.output.exaone_generation_port import ExaoneGenerationPort

logger = logging.getLogger("uvicorn.error")


class ExaoneGenerationInteractor(ExaoneGenerationUseCase):
    def __init__(self, generator: ExaoneGenerationPort) -> None:
        self._generator = generator

    async def stream_generate(
        self, command: ExaoneGenerationCommand
    ) -> AsyncIterator[str]:
        logger.info(
            "[ontology.exaone_generation] 허브 진입 | prompt_len=%d",
            len(command.prompt),
        )
        chunk_count = 0
        async for chunk in self._generator.stream_generate(command):
            chunk_count += 1
            yield chunk
        logger.info("[ontology.exaone_generation] 허브 완료 | chunks=%d", chunk_count)
