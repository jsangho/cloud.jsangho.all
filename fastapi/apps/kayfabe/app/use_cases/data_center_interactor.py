"""데이터 센터 코디네이터 (Phase 2).

읽어 온 행을 `data_center_stats`에 넘겨 세고, 걸러서 페이지로 자른다.
**여기에 계산 규칙을 적지 않는다** — 규칙은 순수 서비스 한 곳에 있다.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from kayfabe.app.dtos.data_center_dto import (
    AnalyticsResponse,
    BeltDetailResponse,
    BeltHolderResponse,
    BeltReignResponse,
    BeltStatResponse,
    BirthdayBoardResponse,
    BirthdayResponse,
    BrandCountResponse,
    ChampionshipStatsResponse,
    DataCenterCountsResponse,
    DataCenterOverviewResponse,
    EventOptionResponse,
    EventStatResponse,
    ExcludedBeltResponse,
    FirstBeltAgeResponse,
    HolderStatResponse,
    MatchPageQuery,
    MatchPageResponse,
    MatchRowResponse,
    OriginCountResponse,
    OriginsResponse,
    RatedWrestlerResponse,
    StaffDirectoryResponse,
    StaffMemberResponse,
    TrainersResponse,
    WrestlerPageQuery,
    WrestlerPageResponse,
    WrestlerRowResponse,
)
from kayfabe.app.ports.input.data_center_use_case import DataCenterUseCase
from kayfabe.app.ports.output.data_center_repository import DataCenterRepository
from kayfabe.app.services import data_center_stats as stats

logger = logging.getLogger("uvicorn.error")

MAX_PAGE_SIZE = 100
RECENT_MATCH_LIMIT = 5


def _paginate[T](items: list[T], page: int, size: int) -> tuple[list[T], int, int, int]:
    """(잘린 목록, 전체 수, 정규화된 page, 정규화된 size).

    **범위를 벗어난 요청을 에러로 만들지 않는다** — 빈 목록과 전체 수를 돌려주면
    화면이 "그 페이지에는 아무것도 없다"를 그대로 그릴 수 있다.
    """
    size = max(1, min(size, MAX_PAGE_SIZE))
    page = max(1, page)
    start = (page - 1) * size
    return items[start : start + size], len(items), page, size


def _matches_filter(fact: stats.MatchFact, query: MatchPageQuery) -> bool:
    if query.event and fact.event_slug != query.event:
        return False
    if query.status and fact.status.strip().lower() != query.status.strip().lower():
        return False
    if query.competitor:
        needle = stats.normalize(query.competitor).casefold()
        if not any(needle in name.casefold() for name in fact.participants):
            return False
    return True


def _to_match_row(fact: stats.MatchFact) -> MatchRowResponse:
    return MatchRowResponse(
        event_slug=fact.event_slug,
        event_label=fact.event_label,
        month=fact.month,
        year=fact.year,
        match_key=fact.match_key,
        title=fact.title,
        format=fact.format,
        status=fact.status,
        participants=list(fact.participants),
        winner_name=fact.winner_name,
        is_title_match=fact.is_title_match,
    )


class DataCenterInteractor(DataCenterUseCase):
    def __init__(self, data_center_repository: DataCenterRepository) -> None:
        self._repo = data_center_repository

    async def get_overview(self) -> DataCenterOverviewResponse:
        logger.info("[DataCenterInteractor] get_overview -> Repository")
        wrestlers = await self._repo.list_wrestlers()
        matches = await self._repo.list_matches()
        titles = await self._repo.list_title_acquisitions()
        events_total, events_finished = await self._repo.count_events()
        belts = await self._repo.count_championship_belts()

        facts = stats.to_facts(matches)
        finished = [f for f in facts if f.is_finished]
        # **최근 = 목록의 뒤쪽**이다. 경기에 날짜 칼럼이 없고 대회의 달만 있어서
        # (일부는 그 달조차 비어 있다) 시간순을 지어내지 않고 대회 순서를 쓴다.
        recent = list(reversed(finished))[:RECENT_MATCH_LIMIT]

        logger.info(
            "[DataCenterInteractor] get_overview <- wrestlers=%d matches=%d titles=%d",
            len(wrestlers),
            len(matches),
            len(titles),
        )
        return DataCenterOverviewResponse(
            counts=DataCenterCountsResponse(
                wrestlers=len(wrestlers),
                matches=len(matches),
                finished_matches=len(finished),
                events=events_total,
                finished_events=events_finished,
                championship_belts=belts,
                title_acquisitions=len(titles),
            ),
            recent_matches=[_to_match_row(f) for f in recent],
        )

    async def list_wrestlers(self, query: WrestlerPageQuery) -> WrestlerPageResponse:
        logger.info(
            "[DataCenterInteractor] list_wrestlers -> Repository q=%s brand=%s page=%d",
            query.q or "-",
            query.brand or "-",
            query.page,
        )
        wrestlers = await self._repo.list_wrestlers()
        matches = await self._repo.list_matches()
        titles = await self._repo.list_title_acquisitions()

        records = stats.records_by_wrestler(matches)
        title_counts = stats.titles_by_wrestler(titles)
        brands = stats.known_brands(wrestlers)

        rows: list[WrestlerRowResponse] = []
        needle = (query.q or "").strip().casefold()
        wanted_brand = (query.brand or "").strip().casefold()
        # **필터와 무관하게 전체에서 센다** — 칩에 적히는 수가 검색어에 따라
        # 흔들리면 "소개와 다른 선수가 몇 명인가"라는 사실이 흐려진다.
        differs_total = sum(
            1
            for row in wrestlers
            if stats.hometown_differs(row.birth_place, row.billed_from)
        )
        only_differs = (query.hometown or "").strip().casefold() == "differs"
        for row in wrestlers:
            if needle and needle not in row.name.casefold():
                if not (row.real_name and needle in row.real_name.casefold()):
                    continue
            if wanted_brand and (row.brand or "").strip().casefold() != wanted_brand:
                continue
            differs = stats.hometown_differs(row.birth_place, row.billed_from)
            if only_differs and not differs:
                continue
            record = records.get(stats.normalize(row.name), stats.RecordCount())
            rows.append(
                WrestlerRowResponse(
                    name=row.name,
                    brand=row.brand,
                    real_name=row.real_name,
                    birth_date=row.birth_date,
                    birth_place=row.birth_place,
                    billed_from=row.billed_from,
                    hometown_differs=differs,
                    finisher=row.finisher,
                    stable_team=row.stable_team,
                    matches=record.total,
                    wins=record.wins,
                    losses=record.losses,
                    win_rate=record.win_rate,
                    titles=title_counts.get(stats.normalize(row.name), 0),
                )
            )

        # 경기가 많은 선수가 먼저 — 전적이 있는 쪽이 목록의 앞이어야 읽힌다.
        rows.sort(key=lambda r: (-r.matches, -r.titles, r.name))
        page_items, total, page, size = _paginate(rows, query.page, query.size)
        logger.info("[DataCenterInteractor] list_wrestlers <- total=%d", total)
        return WrestlerPageResponse(
            items=page_items,
            total=total,
            page=page,
            size=size,
            brands=brands,
            hometown_differs_total=differs_total,
        )

    async def list_matches(self, query: MatchPageQuery) -> MatchPageResponse:
        logger.info(
            "[DataCenterInteractor] list_matches -> Repository event=%s page=%d",
            query.event or "-",
            query.page,
        )
        matches = await self._repo.list_matches()
        facts = stats.to_facts(matches)

        options = [
            EventOptionResponse(slug=stat.slug, label=stat.label)
            for stat in stats.event_stats(facts)
        ]
        filtered = [f for f in facts if _matches_filter(f, query)]
        page_items, total, page, size = _paginate(filtered, query.page, query.size)
        logger.info("[DataCenterInteractor] list_matches <- total=%d", total)
        return MatchPageResponse(
            items=[_to_match_row(f) for f in page_items],
            total=total,
            page=page,
            size=size,
            events=options,
        )

    async def get_championship_stats(self) -> ChampionshipStatsResponse:
        logger.info("[DataCenterInteractor] get_championship_stats -> Repository")
        titles = await self._repo.list_title_acquisitions()
        current = stats.current_belt_stats(titles)
        holders = stats.top_holders(titles)
        logger.info(
            "[DataCenterInteractor] get_championship_stats <- belts=%d excluded=%d",
            len(current.belts),
            len(current.excluded),
        )
        return ChampionshipStatsResponse(
            total_acquisitions=len(titles),
            belt_count=len(current.belts),
            holder_count=len(stats.titles_by_wrestler(titles)),
            belts=[
                BeltStatResponse(
                    belt_name=b.belt_name,
                    reigns=b.reigns,
                    holders=b.holders,
                    top_holder=b.top_holder,
                    top_holder_reigns=b.top_holder_reigns,
                    former_names=list(b.former_names),
                )
                for b in current.belts
            ],
            top_holders=[
                HolderStatResponse(name=h.name, reigns=h.reigns, belts=h.belts)
                for h in holders
            ],
            excluded_belts=[
                ExcludedBeltResponse(
                    belt_name=e.belt_name, reigns=e.reigns, reason=e.reason
                )
                for e in current.excluded
            ],
        )

    async def get_belt_detail(self, belt_name: str) -> BeltDetailResponse | None:
        logger.info("[DataCenterInteractor] get_belt_detail -> belt=%s", belt_name)
        titles = await self._repo.list_title_acquisitions()
        detail = stats.belt_detail(titles, belt_name)
        if detail is None:
            logger.info("[DataCenterInteractor] get_belt_detail <- 현존하지 않는 벨트")
            return None
        return BeltDetailResponse(
            belt_name=detail.belt_name,
            former_names=list(detail.former_names),
            reigns=detail.reigns,
            holder_count=len(detail.holders),
            holders=[
                BeltHolderResponse(
                    name=h.name,
                    reigns=h.reigns,
                    history=[
                        BeltReignResponse(
                            competitor_name=r.competitor_name,
                            belt_name=r.belt_name,
                            won_at=r.won_at,
                        )
                        for r in h.history
                    ],
                )
                for h in detail.holders
            ],
        )

    async def get_analytics(self) -> AnalyticsResponse:
        logger.info("[DataCenterInteractor] get_analytics -> Repository")
        wrestlers = await self._repo.list_wrestlers()
        matches = await self._repo.list_matches()
        titles = await self._repo.list_title_acquisitions()
        facts = stats.to_facts(matches)
        records = stats.records_by_wrestler(matches)
        ages = stats.first_belt_ages(wrestlers, titles)

        title_matches = sum(1 for f in facts if f.is_title_match)
        logger.info("[DataCenterInteractor] get_analytics <- matches=%d", len(facts))
        return AnalyticsResponse(
            events=[
                EventStatResponse(
                    slug=e.slug,
                    label=e.label,
                    month=e.month,
                    year=e.year,
                    matches=e.matches,
                    finished=e.finished,
                    title_matches=e.title_matches,
                    multi_matches=e.multi_matches,
                )
                for e in stats.event_stats(facts)
            ],
            brands=[
                BrandCountResponse(brand=brand, wrestlers=count)
                for brand, count in stats.brand_distribution(wrestlers)
            ],
            singles_matches=sum(1 for f in facts if f.format == "singles"),
            multi_matches=sum(1 for f in facts if f.format == "multi"),
            title_matches=title_matches,
            non_title_matches=len(facts) - title_matches,
            top_win_rates=[
                RatedWrestlerResponse(
                    name=r.name, wins=r.wins, losses=r.losses, win_rate=r.win_rate
                )
                for r in stats.top_win_rates(records)
            ],
            min_matches_for_rate=stats.MIN_MATCHES_FOR_RATE,
            first_belt_ages=[
                FirstBeltAgeResponse(
                    name=e.name,
                    age=e.age,
                    won_on=e.won_on,
                    belt_name=e.belt_name,
                )
                for e in ages.entries
            ],
            first_belt_age_sample=ages.sample,
            first_belt_title_holders=ages.title_holders,
        )

    async def get_birthdays(self, *, limit: int = 5) -> BirthdayBoardResponse:
        """다가오는 생일.

        **오늘은 KST로 센다.** 보는 사람이 한국에 있고, UTC로 자르면 한국 시각
        0시부터 9시 사이에 생일인 사람이 하루 늦게 뜬다. 대회 `status`가 UTC를
        쓰는 것과 다른 선택인데, 그쪽은 **경기가 열린 현지 시각**이 기준이라
        하루를 양보하는 편이 안전하고 이쪽은 **보는 사람의 오늘**이 기준이다.
        """
        logger.info("[DataCenterInteractor] get_birthdays -> Repository")
        wrestlers = await self._repo.list_wrestlers()
        staff = await self._repo.list_staff()
        # **선수와 비선수를 한 줄에 세운다.** 보는 사람에게 생일은 하나의 달력이고,
        # 둘을 갈라 놓으면 같은 날 두 칸이 생긴다. 어느 쪽인지는 `kind`가 말한다.
        people = [
            *stats.to_birthday_people(wrestlers),
            # 관계자 행은 생일 입력 모양으로 접는다 — 역할이 소속 칸을 대신한다.
            *(
                stats.BirthdayPerson(
                    name=row.name,
                    birth_date=row.birth_date,
                    group=row.group_label,
                    kind="staff",
                    role=row.role,
                )
                for row in staff
            ),
        ]
        today = (datetime.now(UTC) + timedelta(hours=9)).date()
        # 한 번만 센다. 전체를 받아 두면 분모(`dated`)가 그 길이라 두 번 돌 일이 없다.
        ranked = stats.upcoming_birthdays(people, today=today, limit=len(people))
        found = ranked[:limit]
        dated = len(ranked)
        logger.info(
            "[DataCenterInteractor] get_birthdays <- %d건 (생일 아는 사람 %d/%d · "
            "선수 %d + 비선수 %d)",
            len(found),
            dated,
            len(people),
            len(wrestlers),
            len(staff),
        )
        return BirthdayBoardResponse(
            today=today.isoformat(),
            entries=[
                BirthdayResponse(
                    name=b.name,
                    group=b.group,
                    kind=b.kind,
                    role=b.role,
                    month_day=b.month_day,
                    birth_date=b.birth_date,
                    age=b.age,
                    days_away=b.days_away,
                )
                for b in found
            ],
            dated=dated,
            total=len(people),
        )

    async def get_origins(self) -> OriginsResponse:
        logger.info("[DataCenterInteractor] get_origins -> Repository")
        wrestlers = await self._repo.list_wrestlers()
        dist = stats.origin_distribution(wrestlers)
        logger.info(
            "[DataCenterInteractor] get_origins <- 나라 %d · 주 %d · 출신 %d/%d",
            len(dist.countries),
            len(dist.us_states),
            dist.located,
            dist.total,
        )
        return OriginsResponse(
            countries=[
                OriginCountResponse(name=g.name, count=g.count, members=list(g.members))
                for g in dist.countries
            ],
            us_states=[
                OriginCountResponse(name=g.name, count=g.count, members=list(g.members))
                for g in dist.us_states
            ],
            us_state_unknown=dist.us_state_unknown,
            located=dist.located,
            total=dist.total,
        )

    async def get_trainers(self) -> TrainersResponse:
        logger.info("[DataCenterInteractor] get_trainers -> Repository")
        wrestlers = await self._repo.list_wrestlers()
        dist = stats.trainer_distribution(wrestlers)
        logger.info(
            "[DataCenterInteractor] get_trainers <- 트레이너 %d · 아는 선수 %d/%d",
            len(dist.groups),
            dist.known,
            dist.total,
        )
        return TrainersResponse(
            groups=[
                OriginCountResponse(name=g.name, count=g.count, members=list(g.members))
                for g in dist.groups
            ],
            institutions=[
                g.name for g in dist.groups if stats.is_training_institution(g.name)
            ],
            known=dist.known,
            total=dist.total,
        )

    async def get_staff(self) -> StaffDirectoryResponse:
        logger.info("[DataCenterInteractor] get_staff -> Repository")
        directory = stats.staff_directory(await self._repo.list_staff())
        logger.info(
            "[DataCenterInteractor] get_staff <- %d명 · 전직 선수 %d",
            directory.total,
            directory.former_wrestlers,
        )
        return StaffDirectoryResponse(
            members=[
                StaffMemberResponse(
                    name=row.name,
                    korean_name=row.korean_ring_name,
                    group=row.group_label,
                    role=row.role,
                    former_wrestler=stats.is_former_wrestler(row.wrestling_experience),
                )
                for row in directory.rows
            ],
            groups=list(directory.groups),
            former_wrestlers=directory.former_wrestlers,
            total=directory.total,
        )
