"""데이터 센터 응답 스키마 (Phase 2).

**모든 수치는 DB에서 센 값이다.** 없는 값은 `None`으로 나가고 화면이 그 칸을 비운다 —
0이나 임시값으로 채우지 않는다.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class _Camel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class DataCenterCountsSchema(_Camel):
    wrestlers: int
    matches: int
    finished_matches: int = Field(alias="finishedMatches")
    events: int
    finished_events: int = Field(alias="finishedEvents")
    championship_belts: int = Field(alias="championshipBelts")
    """현 챔피언 보드에 올라 있는 벨트 수 (`championship_titles`)."""
    title_acquisitions: int = Field(alias="titleAcquisitions")


class MatchRowSchema(_Camel):
    event_slug: str = Field(alias="eventSlug")
    event_label: str = Field(alias="eventLabel")
    month: int | None = None
    year: int
    match_key: str = Field(alias="matchKey")
    title: str
    format: str
    status: str
    participants: list[str]
    winner_name: str | None = Field(default=None, alias="winnerName")
    """승자를 못 되짚으면 `None`이다 — 태그팀 경기에 흔하다."""
    is_title_match: bool = Field(alias="isTitleMatch")


class DataCenterOverviewSchema(_Camel):
    counts: DataCenterCountsSchema
    recent_matches: list[MatchRowSchema] = Field(alias="recentMatches")


class WrestlerRowSchema(_Camel):
    name: str
    brand: str | None = None
    real_name: str | None = Field(default=None, alias="realName")
    birth_date: str | None = Field(default=None, alias="birthDate")
    finisher: str | None = None
    stable_team: str | None = Field(default=None, alias="stableTeam")
    matches: int
    wins: int
    losses: int
    win_rate: float | None = Field(default=None, alias="winRate")
    """승 / (승+패). **끝난 경기가 없으면 `None`** — 0.0이 아니다."""
    titles: int
    """실제 WWE 벨트 획득 횟수 (`title_acquisitions`)."""


class WrestlerPageSchema(_Camel):
    items: list[WrestlerRowSchema]
    total: int
    page: int
    size: int
    brands: list[str]
    """필터에 세울 브랜드 — **DB에 실제로 있는 값만** 온다 (하드코딩하지 않는다)."""


class EventOptionSchema(_Camel):
    slug: str
    label: str


class MatchPageSchema(_Camel):
    items: list[MatchRowSchema]
    total: int
    page: int
    size: int
    events: list[EventOptionSchema]
    """필터에 세울 대회 — DB에 있는 대회만 온다."""


class BeltStatSchema(_Camel):
    belt_name: str = Field(alias="beltName")
    reigns: int
    holders: int
    top_holder: str | None = Field(default=None, alias="topHolder")
    top_holder_reigns: int = Field(alias="topHolderReigns")


class HolderStatSchema(_Camel):
    name: str
    reigns: int
    belts: int


class ChampionshipStatsSchema(_Camel):
    """**최장 재위는 없다.** `won_at`이 자유 텍스트라 기간을 못 낸다 (§9)."""

    total_acquisitions: int = Field(alias="totalAcquisitions")
    belt_count: int = Field(alias="beltCount")
    holder_count: int = Field(alias="holderCount")
    belts: list[BeltStatSchema]
    top_holders: list[HolderStatSchema] = Field(alias="topHolders")


class EventStatSchema(_Camel):
    slug: str
    label: str
    month: int | None = None
    year: int
    matches: int
    finished: int
    title_matches: int = Field(alias="titleMatches")
    multi_matches: int = Field(alias="multiMatches")


class BrandCountSchema(_Camel):
    brand: str
    wrestlers: int


class RatedWrestlerSchema(_Camel):
    name: str
    wins: int
    losses: int
    win_rate: float = Field(alias="winRate")


class AnalyticsSchema(_Camel):
    events: list[EventStatSchema]
    brands: list[BrandCountSchema]
    singles_matches: int = Field(alias="singlesMatches")
    multi_matches: int = Field(alias="multiMatches")
    title_matches: int = Field(alias="titleMatches")
    non_title_matches: int = Field(alias="nonTitleMatches")
    top_win_rates: list[RatedWrestlerSchema] = Field(alias="topWinRates")
    min_matches_for_rate: int = Field(alias="minMatchesForRate")
    """승률 순위에 오르는 최소 경기 수. **화면이 이 숫자를 함께 적어야** 순위가 읽힌다."""
