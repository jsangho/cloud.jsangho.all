from __future__ import annotations

from abc import ABC, abstractmethod

from manager.app.dtos.receiver_dto import ReceiverCommand, ReceiverItem


class ReceiverUseCase(ABC):
    @abstractmethod
    async def receiver(self, cmd: ReceiverCommand) -> dict[str, int | None]: ...

    @abstractmethod
    async def list_receiver(self) -> list[ReceiverItem]: ...

    @abstractmethod
    async def mark_read(self, item_id: int) -> None: ...
