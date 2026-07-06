from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from titanic.app.dtos.passenger_ruth_validation_dto import (
    RuthValidationQuery,
    RuthValidationResponse,
)
from titanic.app.ports.output.passenger_ruth_validation_port import RuthValidationPort


class RuthValidationRepository(RuthValidationPort):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def introduce_myself(
        self, query: RuthValidationQuery
    ) -> RuthValidationResponse:
        return RuthValidationResponse(
            id=query.id * 10000,
            name=query.name + "가 레포지토리에 다녀옴",
        )
