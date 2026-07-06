from __future__ import annotations

from abc import ABC, abstractmethod

from titanic.app.dtos.passenger_ruth_validation_dto import (
    RuthValidationQuery,
    RuthValidationResponse,
)


class RuthValidationPort(ABC):
    @abstractmethod
    async def introduce_myself(
        self, query: RuthValidationQuery
    ) -> RuthValidationResponse:
        pass
