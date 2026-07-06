from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from titanic.app.dtos.passenger_cal_tester_dto import CalTesterQuery, CalTesterResponse


class CalTesterUseCase(ABC):
    """`/titanic/cal/*` inbound(cal_tester_router) 입력 포트."""

    @abstractmethod
    async def test_model(self, test_set) -> dict[str, Any]:
        """칼 테스터가 제안할 모델들을 테스트하는 메소드"""
        ...

    @abstractmethod
    async def introduce_myself(self, query: CalTesterQuery) -> CalTesterResponse:
        """캘던 하클리의 자기소개 메소드 (`GET /myself`)."""
        ...
