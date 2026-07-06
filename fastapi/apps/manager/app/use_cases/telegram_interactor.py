from __future__ import annotations

from manager.app.dtos.telegram_dto import (
    TelegramQuery,
    TelegramResponse,
    TelegramSendCommand,
)
from manager.app.ports.input.telegram_use_case import TelegramUseCase
from manager.app.ports.output.telegram_repository import TelegramRepository


class TelegramInteractor(TelegramUseCase):
    def __init__(self, repository: TelegramRepository) -> None:
        self._repository = repository

    async def introduce_myself(self, query: TelegramQuery) -> TelegramResponse:
        return await self._repository.introduce_myself(query)

    async def send_message(self, cmd: TelegramSendCommand) -> dict[str, str]:
        return await self._repository.send_message(cmd)
