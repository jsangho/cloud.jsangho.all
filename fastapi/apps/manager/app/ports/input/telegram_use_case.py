from __future__ import annotations

from abc import ABC, abstractmethod

from manager.app.dtos.telegram_dto import (
    TelegramQuery,
    TelegramResponse,
    TelegramSendCommand,
)


class TelegramUseCase(ABC):
    """`/manager/telegram/*` inbound 입력 포트."""

    @abstractmethod
    async def introduce_myself(self, query: TelegramQuery) -> TelegramResponse:
        """Telegram 서비스 자기소개."""
        ...

    @abstractmethod
    async def send_message(self, cmd: TelegramSendCommand) -> dict[str, str]:
        """Telegram 메시지 전송."""
        ...
