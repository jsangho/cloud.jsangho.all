from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from titanic.app.dtos.crew_andrews_architect_dto import (
    AndrewsArchitectQuery,
    AndrewsArchitectResponse,
)


class AndrewsArchitectPort(ABC):
    """Andrews Architect 출력 포트."""

    @abstractmethod
    def analyze_intent(self, messages: list[str]) -> dict[str, Any]:
        """Kiwi 형태소 분석으로 질문 의도를 파악하는 추상 메소드"""
        pass

    @abstractmethod
    async def introduce_myself(
        self, query: AndrewsArchitectQuery
    ) -> AndrewsArchitectResponse:
        """앤드류스 자기소개 저장소 메소드."""
        ...
