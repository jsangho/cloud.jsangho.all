"""데이터 센터 입력 포트 (Phase 2)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from kayfabe.app.dtos.data_center_dto import (
    AnalyticsResponse,
    ChampionshipStatsResponse,
    DataCenterOverviewResponse,
    MatchPageQuery,
    MatchPageResponse,
    WrestlerPageQuery,
    WrestlerPageResponse,
)


class DataCenterUseCase(ABC):
    """`/data-center/*` inbound(data_center_router) 입력 포트."""

    @abstractmethod
    async def get_overview(self) -> DataCenterOverviewResponse: ...

    @abstractmethod
    async def list_wrestlers(
        self, query: WrestlerPageQuery
    ) -> WrestlerPageResponse: ...

    @abstractmethod
    async def list_matches(self, query: MatchPageQuery) -> MatchPageResponse: ...

    @abstractmethod
    async def get_championship_stats(self) -> ChampionshipStatsResponse: ...

    @abstractmethod
    async def get_analytics(self) -> AnalyticsResponse: ...
