from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from titanic.app.dtos.crew_andrews_architect_dto import (
    AndrewsArchitectQuery,
    AndrewsArchitectResponse,
)


class AndrewsArchitectUseCase(ABC):
    """`/titanic/andrews/*` inbound(andrews_architect_router) 입력 포트."""

    @abstractmethod
    def analyze_intent(self, question: str) -> dict[str, Any]:
        """Kiwi 형태소 분석으로 프론트 질문의 의도를 파악하는 추상 메소드"""
        pass

    @abstractmethod
    async def introduce_myself(
        self, query: AndrewsArchitectQuery
    ) -> AndrewsArchitectResponse:
        """앤드류스 자기소개 메소드 (`GET /myself`)."""
        ...
