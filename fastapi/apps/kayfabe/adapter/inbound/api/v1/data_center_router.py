"""데이터 센터 라우터 (Phase 2).

**DB가 원본이다** (§1). 홈 KPI가 쓰는 `/ple-matches/competitors`(정적 로스터 166명)와
달리 여기의 선수 수는 `wrestlers` 표를 센 값이다 — 둘은 다른 뜻이고, 그 차이를
숫자로 맞추려고 어느 한쪽을 보정하지 않는다.

DTO → 스키마 매핑은 인접한 `ai_prediction_router`·`ai_lab_router`와 같이 **여기서** 한다.
app 레이어가 Pydantic을 모르게 두기 위해서다(CLAUDE.md §0-2) — 예전에 DTO가 스키마를
import하던 구조는 `kayfabe.adapter.inbound.api` 패키지를 거쳐 이 라우터로 되돌아오는
순환이었다.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query
from kayfabe.adapter.inbound.api.schemas.data_center_schema import (
    AnalyticsSchema,
    BeltStatSchema,
    BrandCountSchema,
    ChampionshipStatsSchema,
    DataCenterCountsSchema,
    DataCenterOverviewSchema,
    EventOptionSchema,
    EventStatSchema,
    HolderStatSchema,
    MatchPageSchema,
    MatchRowSchema,
    RatedWrestlerSchema,
    WrestlerPageSchema,
    WrestlerRowSchema,
)
from kayfabe.app.dtos.data_center_dto import (
    AnalyticsResponse,
    BeltStatResponse,
    BrandCountResponse,
    ChampionshipStatsResponse,
    DataCenterCountsResponse,
    DataCenterOverviewResponse,
    EventOptionResponse,
    EventStatResponse,
    HolderStatResponse,
    MatchPageQuery,
    MatchPageResponse,
    MatchRowResponse,
    RatedWrestlerResponse,
    WrestlerPageQuery,
    WrestlerPageResponse,
    WrestlerRowResponse,
)
from kayfabe.app.ports.input.data_center_use_case import DataCenterUseCase
from kayfabe.dependencies.data_center_provider import get_data_center

logger = logging.getLogger("uvicorn.error")

data_center_router = APIRouter(prefix="/data-center", tags=["data-center"])


@data_center_router.get(
    "/overview",
    response_model=DataCenterOverviewSchema,
    response_model_by_alias=True,
)
async def get_overview(use_case: DataCenterUseCase = Depends(get_data_center)):
    """선수·경기·대회·챔피언십 카운트와 최근 경기."""
    logger.info("[DataCenterRouter] get_overview")
    return overview_to_schema(await use_case.get_overview())


@data_center_router.get(
    "/wrestlers",
    response_model=WrestlerPageSchema,
    response_model_by_alias=True,
)
async def list_wrestlers(
    q: str | None = None,
    brand: str | None = None,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=24, ge=1, le=100),
    use_case: DataCenterUseCase = Depends(get_data_center),
):
    """DB 선수 목록 + 전적. 검색·브랜드 필터·페이지네이션."""
    logger.info(
        "[DataCenterRouter] list_wrestlers | q=%s brand=%s page=%d",
        q or "-",
        brand or "-",
        page,
    )
    query = WrestlerPageQuery(q=q, brand=brand, page=page, size=size)
    return wrestler_page_to_schema(await use_case.list_wrestlers(query))


@data_center_router.get(
    "/matches",
    response_model=MatchPageSchema,
    response_model_by_alias=True,
)
async def list_matches(
    event: str | None = None,
    competitor: str | None = None,
    status: str | None = None,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    use_case: DataCenterUseCase = Depends(get_data_center),
):
    """경기 목록. 대회·선수·상태 필터와 페이지네이션."""
    logger.info(
        "[DataCenterRouter] list_matches | event=%s competitor=%s page=%d",
        event or "-",
        competitor or "-",
        page,
    )
    query = MatchPageQuery(
        event=event, competitor=competitor, status=status, page=page, size=size
    )
    return match_page_to_schema(await use_case.list_matches(query))


@data_center_router.get(
    "/championships",
    response_model=ChampionshipStatsSchema,
    response_model_by_alias=True,
)
async def get_championship_stats(
    use_case: DataCenterUseCase = Depends(get_data_center),
):
    """벨트별 획득 집계와 최다 획득자.

    **현 챔피언은 여기서 안 준다** — 이미 `GET /api/title-acquisitions/`가 브랜드별
    보드를 준다. 같은 것을 두 곳에서 만들지 않는다.
    """
    logger.info("[DataCenterRouter] get_championship_stats")
    return championship_stats_to_schema(await use_case.get_championship_stats())


@data_center_router.get(
    "/analytics",
    response_model=AnalyticsSchema,
    response_model_by_alias=True,
)
async def get_analytics(use_case: DataCenterUseCase = Depends(get_data_center)):
    """대회별·브랜드별·형식별 분포와 승률 순위."""
    logger.info("[DataCenterRouter] get_analytics")
    return analytics_to_schema(await use_case.get_analytics())


def match_row_to_schema(dto: MatchRowResponse) -> MatchRowSchema:
    return MatchRowSchema(
        event_slug=dto.event_slug,
        event_label=dto.event_label,
        month=dto.month,
        year=dto.year,
        match_key=dto.match_key,
        title=dto.title,
        format=dto.format,
        status=dto.status,
        participants=list(dto.participants),
        winner_name=dto.winner_name,
        is_title_match=dto.is_title_match,
    )


def counts_to_schema(dto: DataCenterCountsResponse) -> DataCenterCountsSchema:
    return DataCenterCountsSchema(
        wrestlers=dto.wrestlers,
        matches=dto.matches,
        finished_matches=dto.finished_matches,
        events=dto.events,
        finished_events=dto.finished_events,
        championship_belts=dto.championship_belts,
        title_acquisitions=dto.title_acquisitions,
    )


def overview_to_schema(dto: DataCenterOverviewResponse) -> DataCenterOverviewSchema:
    return DataCenterOverviewSchema(
        counts=counts_to_schema(dto.counts),
        recent_matches=[match_row_to_schema(m) for m in dto.recent_matches],
    )


def wrestler_row_to_schema(dto: WrestlerRowResponse) -> WrestlerRowSchema:
    return WrestlerRowSchema(
        name=dto.name,
        brand=dto.brand,
        real_name=dto.real_name,
        birth_date=dto.birth_date,
        finisher=dto.finisher,
        stable_team=dto.stable_team,
        matches=dto.matches,
        wins=dto.wins,
        losses=dto.losses,
        win_rate=dto.win_rate,
        titles=dto.titles,
    )


def wrestler_page_to_schema(dto: WrestlerPageResponse) -> WrestlerPageSchema:
    return WrestlerPageSchema(
        items=[wrestler_row_to_schema(i) for i in dto.items],
        total=dto.total,
        page=dto.page,
        size=dto.size,
        brands=list(dto.brands),
    )


def event_option_to_schema(dto: EventOptionResponse) -> EventOptionSchema:
    return EventOptionSchema(slug=dto.slug, label=dto.label)


def match_page_to_schema(dto: MatchPageResponse) -> MatchPageSchema:
    return MatchPageSchema(
        items=[match_row_to_schema(i) for i in dto.items],
        total=dto.total,
        page=dto.page,
        size=dto.size,
        events=[event_option_to_schema(e) for e in dto.events],
    )


def belt_stat_to_schema(dto: BeltStatResponse) -> BeltStatSchema:
    return BeltStatSchema(
        belt_name=dto.belt_name,
        reigns=dto.reigns,
        holders=dto.holders,
        top_holder=dto.top_holder,
        top_holder_reigns=dto.top_holder_reigns,
    )


def holder_stat_to_schema(dto: HolderStatResponse) -> HolderStatSchema:
    return HolderStatSchema(name=dto.name, reigns=dto.reigns, belts=dto.belts)


def championship_stats_to_schema(
    dto: ChampionshipStatsResponse,
) -> ChampionshipStatsSchema:
    return ChampionshipStatsSchema(
        total_acquisitions=dto.total_acquisitions,
        belt_count=dto.belt_count,
        holder_count=dto.holder_count,
        belts=[belt_stat_to_schema(b) for b in dto.belts],
        top_holders=[holder_stat_to_schema(h) for h in dto.top_holders],
    )


def event_stat_to_schema(dto: EventStatResponse) -> EventStatSchema:
    return EventStatSchema(
        slug=dto.slug,
        label=dto.label,
        month=dto.month,
        year=dto.year,
        matches=dto.matches,
        finished=dto.finished,
        title_matches=dto.title_matches,
        multi_matches=dto.multi_matches,
    )


def brand_count_to_schema(dto: BrandCountResponse) -> BrandCountSchema:
    return BrandCountSchema(brand=dto.brand, wrestlers=dto.wrestlers)


def rated_wrestler_to_schema(dto: RatedWrestlerResponse) -> RatedWrestlerSchema:
    return RatedWrestlerSchema(
        name=dto.name, wins=dto.wins, losses=dto.losses, win_rate=dto.win_rate
    )


def analytics_to_schema(dto: AnalyticsResponse) -> AnalyticsSchema:
    return AnalyticsSchema(
        events=[event_stat_to_schema(e) for e in dto.events],
        brands=[brand_count_to_schema(b) for b in dto.brands],
        singles_matches=dto.singles_matches,
        multi_matches=dto.multi_matches,
        title_matches=dto.title_matches,
        non_title_matches=dto.non_title_matches,
        top_win_rates=[rated_wrestler_to_schema(r) for r in dto.top_win_rates],
        min_matches_for_rate=dto.min_matches_for_rate,
    )
