from __future__ import annotations

import logging
from typing import Annotated

from soccer.adapter.inbound.api.schemas.soccer_chat_schema import SoccerChatSchema
from soccer.app.dtos.soccer_chat_dto import SoccerChatCommand, SoccerChatTurnDto
from soccer.app.ports.input.soccer_chat_use_case import SoccerChatUseCase
from soccer.dependencies.soccer_chat_provider import get_soccer_chat_use_case

from fastapi import APIRouter, Body, Depends
from fastapi.responses import StreamingResponse

logger = logging.getLogger("uvicorn.error")

soccer_chat_router = APIRouter(prefix="/soccer-chat", tags=["soccer-chat"])


@soccer_chat_router.post("/chat")
async def chat(
    schema: Annotated[SoccerChatSchema, Body()],
    use_case: SoccerChatUseCase = Depends(get_soccer_chat_use_case),
) -> StreamingResponse:
    for msg in schema.messages:
        logger.info(
            "[soccer-chat/chat] messages | role=%s | text=%s", msg.role, msg.text
        )
    command = SoccerChatCommand(
        messages=tuple(
            SoccerChatTurnDto(role=msg.role, text=msg.text) for msg in schema.messages
        ),
    )
    return StreamingResponse(
        use_case.stream_chat(command), media_type="text/plain; charset=utf-8"
    )
