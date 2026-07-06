from __future__ import annotations

from abc import ABC, abstractmethod

from titanic.app.dtos.passenger_cal_tester_dto import CalTesterQuery, CalTesterResponse


class CalTesterPort(ABC):
    @abstractmethod
    async def introduce_myself(self, query: CalTesterQuery) -> CalTesterResponse:
        pass
