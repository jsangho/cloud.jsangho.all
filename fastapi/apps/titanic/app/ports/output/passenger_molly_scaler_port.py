from __future__ import annotations

from abc import ABC, abstractmethod

from titanic.app.dtos.passenger_molly_scaler_dto import (
    MollyScalerQuery,
    MollyScalerResponse,
)


class MollyScalerPort(ABC):
    @abstractmethod
    async def introduce_myself(self, query: MollyScalerQuery) -> MollyScalerResponse:
        pass
