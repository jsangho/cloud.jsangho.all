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

from fastapi import APIRouter, Depends, HTTPException, Query

from kayfabe.adapter.inbound.api.schemas.data_center_schema import (
    AnalyticsSchema,
    BeltDetailSchema,
    BeltHolderSchema,
    BeltReignSchema,
    BeltStatSchema,
    BirthdayBoardSchema,
    BirthdaySchema,
    BrandCountSchema,
    ChampionshipStatsSchema,
    DataCenterCountsSchema,
    DataCenterOverviewSchema,
    EventOptionSchema,
    EventStatSchema,
    ExcludedBeltSchema,
    HolderStatSchema,
    MatchPageSchema,
    MatchRowSchema,
    OriginCountSchema,
    OriginsSchema,
    RatedWrestlerSchema,
    StaffDirectorySchema,
    StaffGroupSchema,
    StaffMemberSchema,
    TrainersSchema,
    WrestlerPageSchema,
    WrestlerRowSchema,
)
from kayfabe.app.dtos.data_center_dto import (
    AnalyticsResponse,
    BeltDetailResponse,
    BeltStatResponse,
    BirthdayBoardResponse,
    BrandCountResponse,
    ChampionshipStatsResponse,
    DataCenterCountsResponse,
    DataCenterOverviewResponse,
    EventOptionResponse,
    EventStatResponse,
    ExcludedBeltResponse,
    HolderStatResponse,
    MatchPageQuery,
    MatchPageResponse,
    MatchRowResponse,
    OriginsResponse,
    RatedWrestlerResponse,
    StaffDirectoryResponse,
    TrainersResponse,
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
    "/birthdays",
    response_model=BirthdayBoardSchema,
    response_model_by_alias=True,
)
async def get_birthdays(
    limit: int = Query(default=5, ge=1, le=20),
    use_case: DataCenterUseCase = Depends(get_data_center),
):
    """다가오는 선수 생일.

    **창이 아니라 개수로 자른다** — 로스터 165명으로는 1년 중 239일이 0명이라
    "앞으로 30일" 같은 창은 화면을 자주 통째로 비운다. 날짜가 멀어질지언정
    목록은 비지 않는다.
    """
    logger.info("[DataCenterRouter] get_birthdays | limit=%d", limit)
    return birthday_board_to_schema(await use_case.get_birthdays(limit=limit))


@data_center_router.get(
    "/wrestlers",
    response_model=WrestlerPageSchema,
    response_model_by_alias=True,
)
async def list_wrestlers(
    q: str | None = None,
    brand: str | None = None,
    hometown: str | None = Query(
        default=None,
        description='"differs"면 소개 연고지가 실제 출생지와 다른 선수만',
    ),
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
    query = WrestlerPageQuery(q=q, brand=brand, hometown=hometown, page=page, size=size)
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

    `belts`는 **지금 있는 벨트만** 담는다. 폐지·개명 전 이름의 처리는
    `ChampionshipStatsSchema` 설명 참조.
    """
    logger.info("[DataCenterRouter] get_championship_stats")
    return championship_stats_to_schema(await use_case.get_championship_stats())


@data_center_router.get(
    "/championships/{belt_name}",
    response_model=BeltDetailSchema,
    response_model_by_alias=True,
)
async def get_belt_detail(
    belt_name: str,
    use_case: DataCenterUseCase = Depends(get_data_center),
):
    """벨트 하나의 획득 이력 (보유자별).

    `belt_name`은 **현 챔피언 보드가 쓰는 이름**이다 — 옛 이름으로 물으면 404다.
    옛 이름으로 적힌 획득은 응답 안에 그 이름 그대로 들어 있다.
    """
    logger.info("[DataCenterRouter] get_belt_detail | belt=%s", belt_name)
    detail = await use_case.get_belt_detail(belt_name)
    if detail is None:
        raise HTTPException(status_code=404, detail="현존하는 벨트가 아닙니다")
    return belt_detail_to_schema(detail)


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
        birth_place=dto.birth_place,
        billed_from=dto.billed_from,
        hometown_differs=dto.hometown_differs,
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
        hometown_differs_total=dto.hometown_differs_total,
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
        former_names=dto.former_names,
    )


def excluded_belt_to_schema(dto: ExcludedBeltResponse) -> ExcludedBeltSchema:
    return ExcludedBeltSchema(
        belt_name=dto.belt_name, reigns=dto.reigns, reason=dto.reason
    )


def belt_detail_to_schema(dto: BeltDetailResponse) -> BeltDetailSchema:
    return BeltDetailSchema(
        belt_name=dto.belt_name,
        former_names=dto.former_names,
        reigns=dto.reigns,
        holder_count=dto.holder_count,
        holders=[
            BeltHolderSchema(
                name=h.name,
                reigns=h.reigns,
                history=[
                    BeltReignSchema(
                        competitor_name=r.competitor_name,
                        belt_name=r.belt_name,
                        won_at=r.won_at,
                    )
                    for r in h.history
                ],
            )
            for h in dto.holders
        ],
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
        excluded_belts=[excluded_belt_to_schema(e) for e in dto.excluded_belts],
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


def birthday_board_to_schema(dto: BirthdayBoardResponse) -> BirthdayBoardSchema:
    return BirthdayBoardSchema(
        today=dto.today,
        entries=[
            BirthdaySchema(
                name=e.name,
                group=e.group,
                kind=e.kind,
                role=e.role,
                month_day=e.month_day,
                birth_date=e.birth_date,
                age=e.age,
                days_away=e.days_away,
            )
            for e in dto.entries
        ],
        dated=dto.dated,
        total=dto.total,
    )


def origins_to_schema(dto: OriginsResponse) -> OriginsSchema:
    return OriginsSchema(
        countries=[
            OriginCountSchema(name=c.name, count=c.count, members=list(c.members))
            for c in dto.countries
        ],
        us_states=[
            OriginCountSchema(name=c.name, count=c.count, members=list(c.members))
            for c in dto.us_states
        ],
        us_state_unknown=dto.us_state_unknown,
        located=dto.located,
        total=dto.total,
    )


@data_center_router.get(
    "/origins",
    response_model=OriginsSchema,
    response_model_by_alias=True,
)
async def get_origins(use_case: DataCenterUseCase = Depends(get_data_center)):
    """출신 나라·미국 주 분포 — 지도 둘이 쓴다."""
    logger.info("[DataCenterRouter] get_origins")
    return origins_to_schema(await use_case.get_origins())


def trainers_to_schema(dto: TrainersResponse) -> TrainersSchema:
    return TrainersSchema(
        groups=[
            OriginCountSchema(name=g.name, count=g.count, members=list(g.members))
            for g in dto.groups
        ],
        institutions=list(dto.institutions),
        known=dto.known,
        total=dto.total,
    )


@data_center_router.get(
    "/trainers",
    response_model=TrainersSchema,
    response_model_by_alias=True,
)
async def get_trainers(use_case: DataCenterUseCase = Depends(get_data_center)):
    """누가 누구를 길렀나 — 제자 수 내림차순."""
    logger.info("[DataCenterRouter] get_trainers")
    return trainers_to_schema(await use_case.get_trainers())


def staff_directory_to_schema(dto: StaffDirectoryResponse) -> StaffDirectorySchema:
    return StaffDirectorySchema(
        members=[
            StaffMemberSchema(
                name=m.name,
                korean_name=m.korean_name,
                group=m.group,
                role=m.role,
                former_wrestler=m.former_wrestler,
            )
            for m in dto.members
        ],
        groups=[StaffGroupSchema(name=n, count=c) for n, c in dto.groups],
        former_wrestlers=dto.former_wrestlers,
        total=dto.total,
    )


@data_center_router.get(
    "/staff",
    response_model=StaffDirectorySchema,
    response_model_by_alias=True,
)
async def get_staff(use_case: DataCenterUseCase = Depends(get_data_center)):
    """관계자 명부 — 경영진·해설·심판·프로듀서."""
    logger.info("[DataCenterRouter] get_staff")
    return staff_directory_to_schema(await use_case.get_staff())
