from fastapi import APIRouter, Depends
from manager.adapter.inbound.api.schemas.telegram_schema import (
    TelegramMyselfSchema,
    TelegramSendRequest,
)
from manager.app.dtos.telegram_dto import (
    TelegramQuery,
    TelegramResponse,
    TelegramSendCommand,
)
from manager.app.ports.input.telegram_use_case import TelegramUseCase
from manager.dependencies.telegram_provider import get_telegram_use_case

telegram_router = APIRouter(prefix="/telegram", tags=["telegram"])


@telegram_router.get("/myself")
async def introduce_myself(
    use_case: TelegramUseCase = Depends(get_telegram_use_case),
) -> TelegramResponse:
    schema = TelegramMyselfSchema()
    query = TelegramQuery(id=schema.id, name=schema.name)
    return await use_case.introduce_myself(query)


@telegram_router.post("/send")
async def send_message(
    body: TelegramSendRequest,
    use_case: TelegramUseCase = Depends(get_telegram_use_case),
) -> dict[str, str]:
    cmd = TelegramSendCommand(chat_id=body.chat_id, message=body.message)
    return await use_case.send_message(cmd)
