from __future__ import annotations

from titanic.app.dtos.passenger_molly_scaler_dto import (
    MollyScalerQuery,
    MollyScalerResponse,
)
from titanic.app.ports.input.passenger_molly_scaler_use_case import MollyScalerUseCase
from titanic.app.ports.output.passenger_molly_scaler_port import MollyScalerPort


class MollyScalerInteractor(MollyScalerUseCase):
    def __init__(self, repository: MollyScalerPort):
        self.repository = repository

    async def introduce_myself(self, query: MollyScalerQuery) -> MollyScalerResponse:
        return await self.repository.introduce_myself(query)
