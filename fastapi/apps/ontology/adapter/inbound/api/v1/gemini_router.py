from __future__ import annotations

import logging
from typing import Annotated

from core.matrix.grid_sentinel_stream_guard import open_guarded_text_stream
from fastapi.responses import StreamingResponse

from fastapi import APIRouter, Body, Depends
from ontology.adapter.inbound.api.schemas.gemini_schema import GeminiAskSchema
from ontology.app.dtos.gemini_generation_dto import GeminiGenerationCommand
from ontology.app.ports.input.gemini_generation_use_case import (
    GeminiGenerationUseCase,
)
from ontology.dependencies.gemini_generation_provider import (
    get_gemini_generation_use_case,
)

logger = logging.getLogger("uvicorn.error")

gemini_router = APIRouter(prefix="/gemini", tags=["gemini"])


@gemini_router.post("/ask")
async def ask(
    schema: Annotated[GeminiAskSchema, Body()],
    use_case: GeminiGenerationUseCase = Depends(get_gemini_generation_use_case),
) -> StreamingResponse:
    logger.info("[ontology/gemini/ask] question=%s", schema.question)
    command = GeminiGenerationCommand(prompt=schema.question)
    return await open_guarded_text_stream(
        use_case.stream_generate(command), label="ontology/gemini/ask"
    )
