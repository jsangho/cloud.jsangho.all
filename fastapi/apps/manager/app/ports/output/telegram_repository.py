from __future__ import annotations

from abc import ABC, abstractmethod

from manager.app.dtos.telegram_dto import (
    TelegramQuery,
    TelegramResponse,
    TelegramSendCommand,
)


class TelegramRepository(ABC):
    @abstractmethod
    async def introduce_myself(self, query: TelegramQuery) -> TelegramResponse: ...

    @abstractmethod
    async def send_message(self, cmd: TelegramSendCommand) -> dict[str, str]: ...
