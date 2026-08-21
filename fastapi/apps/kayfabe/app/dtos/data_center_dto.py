"""데이터 센터 DTO — 유스케이스가 주고받는 값 (Phase 2).

스키마와 한 겹 떨어뜨려 두는 이유는 이 앱의 규약이다(§4 네이밍): 도메인·유스케이스는
Pydantic을 모르고, 어댑터가 `to_schema()`로 옮긴다.
"""

from __future__ import annotations

from dataclasses import dataclass, field

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


@dataclass(frozen=True)
class WrestlerPageQuery:
    """목록 질의. **페이지는 1부터**이고 크기는 라우터가 잘라서 넘긴다."""

    q: str | None = None
    brand: str | None = None
    page: int = 1
    size: int = 24


@dataclass(frozen=True)
class MatchPageQuery:
    event: str | None = None
    competitor: str | None = None
    status: str | None = None
    page: int = 1
    size: int = 20


@dataclass(frozen=True)
class MatchRowResponse:
    event_slug: str
    event_label: str
    month: int | None
    year: int
    match_key: str
    title: str
    format: str
    status: str
    participants: list[str]
    winner_name: str | None
    is_title_match: bool

    def to_schema(self) -> MatchRowSchema:
        return MatchRowSchema(
            event_slug=self.event_slug,
            event_label=self.event_label,
            month=self.month,
            year=self.year,
            match_key=self.match_key,
            title=self.title,
            format=self.format,
            status=self.status,
            participants=list(self.participants),
            winner_name=self.winner_name,
            is_title_match=self.is_title_match,
        )


@dataclass(frozen=True)
class DataCenterCountsResponse:
    wrestlers: int
    matches: int
    finished_matches: int
    events: int
    finished_events: int
    championship_belts: int
    title_acquisitions: int

    def to_schema(self) -> DataCenterCountsSchema:
        return DataCenterCountsSchema(
            wrestlers=self.wrestlers,
            matches=self.matches,
            finished_matches=self.finished_matches,
            events=self.events,
            finished_events=self.finished_events,
            championship_belts=self.championship_belts,
            title_acquisitions=self.title_acquisitions,
        )


@dataclass(frozen=True)
class DataCenterOverviewResponse:
    counts: DataCenterCountsResponse
    recent_matches: list[MatchRowResponse] = field(default_factory=list)

    def to_schema(self) -> DataCenterOverviewSchema:
        return DataCenterOverviewSchema(
            counts=self.counts.to_schema(),
            recent_matches=[m.to_schema() for m in self.recent_matches],
        )


@dataclass(frozen=True)
class WrestlerRowResponse:
    name: str
    brand: str | None
    real_name: str | None
    birth_date: str | None
    finisher: str | None
    stable_team: str | None
    matches: int
    wins: int
    losses: int
    win_rate: float | None
    titles: int

    def to_schema(self) -> WrestlerRowSchema:
        return WrestlerRowSchema(
            name=self.name,
            brand=self.brand,
            real_name=self.real_name,
            birth_date=self.birth_date,
            finisher=self.finisher,
            stable_team=self.stable_team,
            matches=self.matches,
            wins=self.wins,
            losses=self.losses,
            win_rate=self.win_rate,
            titles=self.titles,
        )


@dataclass(frozen=True)
class WrestlerPageResponse:
    items: list[WrestlerRowResponse]
    total: int
    page: int
    size: int
    brands: list[str]

    def to_schema(self) -> WrestlerPageSchema:
        return WrestlerPageSchema(
            items=[i.to_schema() for i in self.items],
            total=self.total,
            page=self.page,
            size=self.size,
            brands=list(self.brands),
        )


@dataclass(frozen=True)
class EventOptionResponse:
    slug: str
    label: str

    def to_schema(self) -> EventOptionSchema:
        return EventOptionSchema(slug=self.slug, label=self.label)


@dataclass(frozen=True)
class MatchPageResponse:
    items: list[MatchRowResponse]
    total: int
    page: int
    size: int
    events: list[EventOptionResponse]

    def to_schema(self) -> MatchPageSchema:
        return MatchPageSchema(
            items=[i.to_schema() for i in self.items],
            total=self.total,
            page=self.page,
            size=self.size,
            events=[e.to_schema() for e in self.events],
        )


@dataclass(frozen=True)
class BeltStatResponse:
    belt_name: str
    reigns: int
    holders: int
    top_holder: str | None
    top_holder_reigns: int

    def to_schema(self) -> BeltStatSchema:
        return BeltStatSchema(
            belt_name=self.belt_name,
            reigns=self.reigns,
            holders=self.holders,
            top_holder=self.top_holder,
            top_holder_reigns=self.top_holder_reigns,
        )


@dataclass(frozen=True)
class HolderStatResponse:
    name: str
    reigns: int
    belts: int

    def to_schema(self) -> HolderStatSchema:
        return HolderStatSchema(name=self.name, reigns=self.reigns, belts=self.belts)


@dataclass(frozen=True)
class ChampionshipStatsResponse:
    total_acquisitions: int
    belt_count: int
    holder_count: int
    belts: list[BeltStatResponse]
    top_holders: list[HolderStatResponse]

    def to_schema(self) -> ChampionshipStatsSchema:
        return ChampionshipStatsSchema(
            total_acquisitions=self.total_acquisitions,
            belt_count=self.belt_count,
            holder_count=self.holder_count,
            belts=[b.to_schema() for b in self.belts],
            top_holders=[h.to_schema() for h in self.top_holders],
        )


@dataclass(frozen=True)
class EventStatResponse:
    slug: str
    label: str
    month: int | None
    year: int
    matches: int
    finished: int
    title_matches: int
    multi_matches: int

    def to_schema(self) -> EventStatSchema:
        return EventStatSchema(
            slug=self.slug,
            label=self.label,
            month=self.month,
            year=self.year,
            matches=self.matches,
            finished=self.finished,
            title_matches=self.title_matches,
            multi_matches=self.multi_matches,
        )


@dataclass(frozen=True)
class BrandCountResponse:
    brand: str
    wrestlers: int

    def to_schema(self) -> BrandCountSchema:
        return BrandCountSchema(brand=self.brand, wrestlers=self.wrestlers)


@dataclass(frozen=True)
class RatedWrestlerResponse:
    name: str
    wins: int
    losses: int
    win_rate: float

    def to_schema(self) -> RatedWrestlerSchema:
        return RatedWrestlerSchema(
            name=self.name, wins=self.wins, losses=self.losses, win_rate=self.win_rate
        )


@dataclass(frozen=True)
class AnalyticsResponse:
    events: list[EventStatResponse]
    brands: list[BrandCountResponse]
    singles_matches: int
    multi_matches: int
    title_matches: int
    non_title_matches: int
    top_win_rates: list[RatedWrestlerResponse]
    min_matches_for_rate: int

    def to_schema(self) -> AnalyticsSchema:
        return AnalyticsSchema(
            events=[e.to_schema() for e in self.events],
            brands=[b.to_schema() for b in self.brands],
            singles_matches=self.singles_matches,
            multi_matches=self.multi_matches,
            title_matches=self.title_matches,
            non_title_matches=self.non_title_matches,
            top_win_rates=[r.to_schema() for r in self.top_win_rates],
            min_matches_for_rate=self.min_matches_for_rate,
        )
