from __future__ import annotations

from abc import ABC, abstractmethod

from manager.app.dtos.juso_dto import ContactListItem, ContactRecordCommand


class JusoRepository(ABC):
    @abstractmethod
    async def upload_contacts(self, commands: list[ContactRecordCommand]) -> int: ...

    @abstractmethod
    async def list_contacts(self) -> list[ContactListItem]: ...

    @abstractmethod
    async def delete_all_contacts(self) -> int: ...
