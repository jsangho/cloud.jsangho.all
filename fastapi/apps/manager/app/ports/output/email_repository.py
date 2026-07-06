from __future__ import annotations

from abc import ABC, abstractmethod

from manager.app.dtos.email_dto import EmailDto


class EmailRepository(ABC):
    @abstractmethod
    async def save(self, dto: EmailDto, status: str) -> int: ...
