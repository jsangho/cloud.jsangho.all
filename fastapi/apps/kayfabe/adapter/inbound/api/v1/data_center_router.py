"""데이터 센터 라우터 (Phase 2).

**DB가 원본이다** (§1). 홈 KPI가 쓰는 `/ple-matches/competitors`(정적 로스터 166명)와
달리 여기의 선수 수는 `wrestlers` 표를 센 값이다 — 둘은 다른 뜻이고, 그 차이를
숫자로 맞추려고 어느 한쪽을 보정하지 않는다.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query
from kayfabe.adapter.inbound.api.schemas.data_center_schema import (
    AnalyticsSchema,
    ChampionshipStatsSchema,
    DataCenterOverviewSchema,
    MatchPageSchema,
    WrestlerPageSchema,
)
from kayfabe.app.dtos.data_center_dto import MatchPageQuery, WrestlerPageQuery
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
    return (await use_case.get_overview()).to_schema()


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
    return (await use_case.list_wrestlers(query)).to_schema()


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
    return (await use_case.list_matches(query)).to_schema()


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
    return (await use_case.get_championship_stats()).to_schema()


@data_center_router.get(
    "/analytics",
    response_model=AnalyticsSchema,
    response_model_by_alias=True,
)
async def get_analytics(use_case: DataCenterUseCase = Depends(get_data_center)):
    """대회별·브랜드별·형식별 분포와 승률 순위."""
    logger.info("[DataCenterRouter] get_analytics")
    return (await use_case.get_analytics()).to_schema()
