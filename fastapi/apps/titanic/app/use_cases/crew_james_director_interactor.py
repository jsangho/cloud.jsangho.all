from __future__ import annotations

from typing import Any

from titanic.app.dtos.crew_james_director_dto import (
    BookingCommand,
    JamesDirectorQuery,
    JamesDirectorResponse,
    PersonCommand,
    TitanicRecordCommand,
)
from titanic.app.ports.input.crew_james_director_use_case import JamesDirectorUseCase
from titanic.app.ports.output.crew_james_director_port import JamesDirectorPort


class JamesDirectorInteractor(JamesDirectorUseCase):
    """James Director CSV 업로드 유스케이스."""

    def __init__(self, repository: JamesDirectorPort) -> None:
        self.repository = repository

    async def introduce_myself(
        self, query: JamesDirectorQuery
    ) -> JamesDirectorResponse:
        """제임스 감독의 자기소개 인터렉트"""

        return await self.repository.introduce_myself(query)

    async def upload_titanic_file(
        self, records: list[TitanicRecordCommand]
    ) -> dict[str, int]:
        return await self.receiver_uploaded_records(records)

    async def receiver_uploaded_records(
        self,
        records: list[TitanicRecordCommand],
        *,
        filename: str = "",
    ) -> dict[str, Any]:
        person_commands: list[PersonCommand] = []
        booking_commands: list[BookingCommand] = []

        for record in records:
            person_commands.append(
                PersonCommand(
                    passenger_id=record.passenger_id or "",
                    name=record.name or "",
                    gender=record.gender or "",
                    age=record.age or "",
                    sib_sp=record.sib_sp or "",
                    parch=record.parch or "",
                    survived=record.survived or "",
                )
            )
            booking_commands.append(
                BookingCommand(
                    pclass=record.pclass or "",
                    ticket=record.ticket or "",
                    fare=record.fare or "",
                    cabin=record.cabin or "",
                    embarked=record.embarked or "",
                )
            )

        count = await self.repository.upload_titanic_file(
            person_commands=person_commands,
            booking_commands=booking_commands,
            filename=filename,
        )
        return {"count": count}
