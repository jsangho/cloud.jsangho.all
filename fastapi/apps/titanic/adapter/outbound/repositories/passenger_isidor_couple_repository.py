from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from titanic.app.dtos.passenger_isidor_couple_dto import (
    IsidorCoupleQuery,
    IsidorCoupleResponse,
)
from titanic.app.ports.output.passenger_isidor_couple_port import IsidorCouplePort


class IsidorCoupleRepository(IsidorCouplePort):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def introduce_myself(self, query: IsidorCoupleQuery) -> IsidorCoupleResponse:
        return IsidorCoupleResponse(
            id=query.id * 10000,
            name=query.name + "가 레포지토리에 다녀옴",
        )
