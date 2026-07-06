from __future__ import annotations

from abc import ABC, abstractmethod

from titanic.app.dtos.passenger_ruth_validation_dto import (
    RuthValidationQuery,
    RuthValidationResponse,
)


class RuthValidationUseCase(ABC):
    """`/titanic/ruth/*` inbound(ruth_validation_router) 입력 포트."""

    @abstractmethod
    async def introduce_myself(
        self, query: RuthValidationQuery
    ) -> RuthValidationResponse:
        """루스 드윗 부카터의 자기소개 메소드 (`GET /myself`)."""
        ...
