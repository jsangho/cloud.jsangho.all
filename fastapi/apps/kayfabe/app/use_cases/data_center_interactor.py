"""데이터 센터 코디네이터 (Phase 2).

읽어 온 행을 `data_center_stats`에 넘겨 세고, 걸러서 페이지로 자른다.
**여기에 계산 규칙을 적지 않는다** — 규칙은 순수 서비스 한 곳에 있다.
"""

from __future__ import annotations

import logging

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
        for row in wrestlers:
            if needle and needle not in row.name.casefold():
                if not (row.real_name and needle in row.real_name.casefold()):
                    continue
            if wanted_brand and (row.brand or "").strip().casefold() != wanted_brand:
                continue
            record = records.get(stats.normalize(row.name), stats.RecordCount())
            rows.append(
                WrestlerRowResponse(
                    name=row.name,
                    brand=row.brand,
                    real_name=row.real_name,
                    birth_date=row.birth_date,
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
            items=page_items, total=total, page=page, size=size, brands=brands
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
        belts = stats.belt_stats(titles)
        holders = stats.top_holders(titles)
        logger.info(
            "[DataCenterInteractor] get_championship_stats <- belts=%d", len(belts)
        )
        return ChampionshipStatsResponse(
            total_acquisitions=len(titles),
            belt_count=len(belts),
            holder_count=len(stats.titles_by_wrestler(titles)),
            belts=[
                BeltStatResponse(
                    belt_name=b.belt_name,
                    reigns=b.reigns,
                    holders=b.holders,
                    top_holder=b.top_holder,
                    top_holder_reigns=b.top_holder_reigns,
                )
                for b in belts
            ],
            top_holders=[
                HolderStatResponse(name=h.name, reigns=h.reigns, belts=h.belts)
                for h in holders
            ],
        )

    async def get_analytics(self) -> AnalyticsResponse:
        logger.info("[DataCenterInteractor] get_analytics -> Repository")
        wrestlers = await self._repo.list_wrestlers()
        matches = await self._repo.list_matches()
        facts = stats.to_facts(matches)
        records = stats.records_by_wrestler(matches)

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
        )
