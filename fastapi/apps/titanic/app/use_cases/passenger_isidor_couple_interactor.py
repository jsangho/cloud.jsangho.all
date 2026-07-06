from __future__ import annotations

from titanic.app.dtos.passenger_isidor_couple_dto import (
    IsidorCoupleQuery,
    IsidorCoupleResponse,
)
from titanic.app.ports.input.passenger_isidor_couple_use_case import IsidorCoupleUseCase
from titanic.app.ports.output.passenger_isidor_couple_port import IsidorCouplePort


class IsidorCoupleInteractor(IsidorCoupleUseCase):
    def __init__(self, repository: IsidorCouplePort):
        self.repository = repository

    async def introduce_myself(self, query: IsidorCoupleQuery) -> IsidorCoupleResponse:
        return await self.repository.introduce_myself(query)
