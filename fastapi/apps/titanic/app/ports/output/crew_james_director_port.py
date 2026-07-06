from __future__ import annotations

from abc import ABC, abstractmethod

from titanic.app.dtos.crew_james_director_dto import (
    BookingCommand,
    JamesDirectorQuery,
    JamesDirectorResponse,
    PersonCommand,
)


class JamesDirectorPort(ABC):
    @abstractmethod
    async def introduce_myself(
        self, query: JamesDirectorQuery
    ) -> JamesDirectorResponse:
        pass

    @abstractmethod
    async def upload_titanic_file(
        self,
        *,
        person_commands: list[PersonCommand],
        booking_commands: list[BookingCommand],
        filename: str,
    ) -> int: ...
