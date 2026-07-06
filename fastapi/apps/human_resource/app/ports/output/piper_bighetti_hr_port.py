from __future__ import annotations

from abc import ABC, abstractmethod

from human_resource.app.dtos.piper_bighetti_hr_dto import (
    BighettiHrQuery,
    BighettiHrResponse,
)


class BighettiHrPort(ABC):
    @abstractmethod
    async def introduce_myself(self, query: BighettiHrQuery) -> BighettiHrResponse:
        pass
