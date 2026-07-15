from __future__ import annotations

import logging
from typing import Annotated

from fastapi.responses import StreamingResponse

from fastapi import APIRouter, Body, Depends
from kayfabe.adapter.inbound.api.schemas.wrestler_chat_schema import (
    WrestlerChatSchema,
)
from kayfabe.app.dtos.wrestler_chat_dto import WrestlerChatCommand, WrestlerChatTurnDto
from kayfabe.app.ports.input.wrestler_chat_use_case import WrestlerChatUseCase
from kayfabe.dependencies.wrestler_chat_provider import get_wrestler_chat_use_case

logger = logging.getLogger("uvicorn.error")

"""
고릴라 포지션 (Gorilla Position)
선수들이 입장 직전 대기하는 백스테이지 자리. WWE 로스터 정보를 RAG로 답한다.
"""
wrestler_chat_router = APIRouter(prefix="/wwe-chat", tags=["wwe-chat"])


@wrestler_chat_router.post("/chat")
async def chat(
    schema: Annotated[WrestlerChatSchema, Body()],
    use_case: WrestlerChatUseCase = Depends(get_wrestler_chat_use_case),
) -> StreamingResponse:
    for msg in schema.messages:
        logger.info("[wwe-chat/chat] messages | role=%s | text=%s", msg.role, msg.text)
    command = WrestlerChatCommand(
        messages=tuple(
            WrestlerChatTurnDto(role=msg.role, text=msg.text) for msg in schema.messages
        ),
    )
    return StreamingResponse(
        use_case.stream_chat(command), media_type="text/plain; charset=utf-8"
    )
