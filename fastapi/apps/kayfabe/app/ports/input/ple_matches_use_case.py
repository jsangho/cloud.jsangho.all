from __future__ import annotations

from abc import ABC, abstractmethod

from kayfabe.app.dtos.ple_matches_dto import (
    CompetitorListResponse,
    CompetitorProfileResponse,
)


class PleMatchesUseCase(ABC):
    """`/records/*` inbound(ple_matches_router > records_router) 입력 포트."""

    @abstractmethod
    async def list_competitors(self, *, q: str | None = None) -> CompetitorListResponse:
        """Neon에 동기화된 PLE 카드 기준 출전 선수 목록."""
        ...

    @abstractmethod
    async def get_competitor_profile(self, name: str) -> CompetitorProfileResponse:
        """선수별 PLE 승패 기록."""
        ...
