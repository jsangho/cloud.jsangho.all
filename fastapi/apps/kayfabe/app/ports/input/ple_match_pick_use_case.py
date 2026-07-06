from __future__ import annotations

from abc import ABC, abstractmethod

from kayfabe.app.dtos.ple_match_pick_dto import RankingsResponse


class PleMatchPickUseCase(ABC):
    """`/rankings` inbound(ple_match_pick_router > ranking_router) 입력 포트."""

    @abstractmethod
    async def list_rankings(
        self,
        *,
        limit: int = 120,
        nickname: str | None = None,
    ) -> RankingsResponse:
        """PLE 예측 순위 (점수·적중률)."""
        ...
