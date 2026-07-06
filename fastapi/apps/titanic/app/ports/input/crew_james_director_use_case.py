from __future__ import annotations

from abc import ABC, abstractmethod

from titanic.app.dtos.crew_james_director_dto import (
    JamesDirectorQuery,
    JamesDirectorResponse,
    TitanicRecordCommand,
)


class JamesDirectorUseCase(ABC):
    """`/titanic/james/*` inbound(james_director_router) 입력 포트."""

    @abstractmethod
    async def upload_titanic_file(
        self, records: list[TitanicRecordCommand]
    ) -> dict[str, int]:
        """CSV 업로드 (`POST /fileupload`)."""
        ...

    @abstractmethod
    async def introduce_myself(
        self, query: JamesDirectorQuery
    ) -> JamesDirectorResponse:
        """제임스 자기소개 메소드 (`GET /myself`)."""
        ...
