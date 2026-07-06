from __future__ import annotations

from abc import ABC, abstractmethod

from titanic.app.dtos.passenger_isidor_couple_dto import (
    IsidorCoupleQuery,
    IsidorCoupleResponse,
)


class IsidorCouplePort(ABC):
    @abstractmethod
    async def introduce_myself(self, query: IsidorCoupleQuery) -> IsidorCoupleResponse:
        pass
