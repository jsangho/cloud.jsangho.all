from __future__ import annotations

from abc import ABC, abstractmethod

from titanic.app.dtos.passenger_molly_scaler_dto import (
    MollyScalerQuery,
    MollyScalerResponse,
)


class MollyScalerUseCase(ABC):
    """`/titanic/molly/*` inbound(molly_scaler_router) 입력 포트."""

    @abstractmethod
    async def introduce_myself(self, query: MollyScalerQuery) -> MollyScalerResponse:
        """몰리 브라운의 자기소개 메소드 (`GET /myself`)."""
        ...
