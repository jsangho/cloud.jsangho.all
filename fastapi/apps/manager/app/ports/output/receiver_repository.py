from __future__ import annotations

from abc import ABC, abstractmethod

from manager.app.dtos.receiver_dto import ReceiverCommand, ReceiverItem


class ReceiverRepository(ABC):
    @abstractmethod
    async def save(
        self, cmd: ReceiverCommand, spam_label: str, spam_confidence: float
    ) -> int: ...

    @abstractmethod
    async def list_all(self) -> list[ReceiverItem]: ...

    @abstractmethod
    async def mark_read(self, item_id: int) -> None: ...
