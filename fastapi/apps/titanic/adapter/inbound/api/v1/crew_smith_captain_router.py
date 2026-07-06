from logging import getLogger
from typing import Annotated

from fastapi import APIRouter, Body, Depends
from fastapi.responses import PlainTextResponse
from titanic.adapter.inbound.api.schemas.crew_smith_captain_schema import (
    ChatSchema,
)
from titanic.app.dtos.crew_smith_captain_dto import (
    SmithCaptainChatCommand,
    SmithCaptainChatTurnDto,
    SmithCaptainQuery,
    SmithCaptainResponse,
)
from titanic.app.ports.input.crew_smith_captain_use_case import SmithCaptainUseCase
from titanic.dependencies.crew_smith_captain_provider import get_smith_captain

logger = getLogger(__name__)

"""
스미스 선장 (Captain Edward John Smith)
타이타닉의 총책임자. 침몰하는 배와 운명을 함께한 명장.
"""
smith_captain_router = APIRouter(prefix="/smith", tags=["smith"])


@smith_captain_router.post("/chat")
async def chat(
    schema: Annotated[ChatSchema, Body()],
    smith: SmithCaptainUseCase = Depends(get_smith_captain),
) -> PlainTextResponse:
    for msg in schema.messages:
        logger.info("[smith/chat] messages | role=%s | text=%s", msg.role, msg.text)
    command = SmithCaptainChatCommand(
        messages=tuple(
            SmithCaptainChatTurnDto(role=msg.role, text=msg.text)
            for msg in schema.messages
        ),
    )
    response = await smith.chat(command=command)
    return PlainTextResponse(content=response)


@smith_captain_router.get("/myself")
async def introduce_myself(
    smith: SmithCaptainUseCase = Depends(get_smith_captain),
) -> SmithCaptainResponse:
    return await smith.introduce_myself(
        SmithCaptainQuery(
            id=5,
            name="Captain Edward John Smith",
        )
    )
