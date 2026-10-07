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
    former_names: list[str] = Field(alias="formerNames")
    """이 집계에 합쳐진 옛 이름 (`belt_lineage`)."""


class ExcludedBeltSchema(_Camel):
    """현 벨트로 이어지지 않아 집계에서 뺀 이름."""

    belt_name: str = Field(alias="beltName")
    reigns: int
    reason: str


class HolderStatSchema(_Camel):
    name: str
    reigns: int
    belts: int


class ChampionshipStatsSchema(_Camel):
    """**최장 재위는 없다.** `won_at`이 자유 텍스트라 기간을 못 낸다 (§9).

    `belts`는 **현 챔피언 보드에 있는 벨트만** 담는다 (2026-10-07 사용자 결정).
    폐지·개명 전 이름은 `belt_lineage`를 따라 후신으로 합치거나 `excluded_belts`로
    빠진다. `total_acquisitions`·`holder_count`·`top_holders`는 **폐지 벨트까지 포함한
    전체 기록**이다 — 두 범위가 섞이지 않게 화면이 그 차이를 적는다.
    """

    total_acquisitions: int = Field(alias="totalAcquisitions")
    belt_count: int = Field(alias="beltCount")
    holder_count: int = Field(alias="holderCount")
    belts: list[BeltStatSchema]
    top_holders: list[HolderStatSchema] = Field(alias="topHolders")
    excluded_belts: list[ExcludedBeltSchema] = Field(alias="excludedBelts")


class BeltReignSchema(_Camel):
    """획득 한 건. `belt_name`은 **그때 불리던 이름**이다."""

    competitor_name: str = Field(alias="competitorName")
    belt_name: str = Field(alias="beltName")
    won_at: str = Field(alias="wonAt")


class BeltHolderSchema(_Camel):
    name: str
    reigns: int
    history: list[BeltReignSchema]


class BeltDetailSchema(_Camel):
    """벨트 하나의 획득 이력. **시간순이 아니라 획득 횟수 순**이다 (§9)."""

    belt_name: str = Field(alias="beltName")
    former_names: list[str] = Field(alias="formerNames")
    reigns: int
    holder_count: int = Field(alias="holderCount")
    holders: list[BeltHolderSchema]


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
