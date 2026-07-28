from admin.adapter.inbound.api.schemas.langchain_chat_schema import (
    LangchainChatRequestSchema,
    LangchainChatResponseSchema,
)
from admin.app.dtos.langchain_chat_dto import LangchainChatCommand, LangchainChatMessage
from admin.app.ports.input.langchain_use_case import LangchainUseCase
from admin.dependencies.langchain_provider import get_langchain_use_case

from fastapi import APIRouter, Depends

langchain_router = APIRouter(prefix="/langchain", tags=["langchain"])


@langchain_router.post("/chat", response_model=LangchainChatResponseSchema)
async def chat(
    request: LangchainChatRequestSchema,
    use_case: LangchainUseCase = Depends(get_langchain_use_case),
) -> LangchainChatResponseSchema:
    command = LangchainChatCommand(
        messages=tuple(
            LangchainChatMessage(role=m.role, text=m.text) for m in request.messages
        )
    )
    result = await use_case.chat(command)
    return LangchainChatResponseSchema(reply=result.reply)
