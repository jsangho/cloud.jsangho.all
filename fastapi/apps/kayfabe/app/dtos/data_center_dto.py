"""데이터 센터 DTO — 유스케이스가 주고받는 값 (Phase 2).

**Pydantic 스키마를 import하지 않는다.** 예전에는 여기서 `to_schema()`를 들고 있었는데,
그러면 app 레이어가 adapter를 향해 의존이 뒤집힌다(CLAUDE.md §0-2). 그리고 그 역방향이
실제로 순환을 만들었다:

    dto → api.schemas.data_center_schema → `kayfabe.adapter.inbound.api` 패키지 __init__
        → data_center_router → dto (아직 실행 중)

`import kayfabe.app.dtos.data_center_dto` 하나만으로 `ImportError`가 났다. 테스트에서는
다른 모듈이 먼저 패키지를 깨워 줘서 드러나지 않았을 뿐이다.

매핑은 인접한 `ai_prediction_router`·`ai_lab_router`와 같은 자리 — **라우터가 한다.**
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class WrestlerPageQuery:
    """목록 질의. **페이지는 1부터**이고 크기는 라우터가 잘라서 넘긴다."""

    q: str | None = None
    brand: str | None = None
    #: `"differs"`면 소개 연고지가 실제 출생지와 다른 선수만. 그 외 값은 무시한다.
    hometown: str | None = None
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


@dataclass(frozen=True)
class DataCenterCountsResponse:
    wrestlers: int
    matches: int
    finished_matches: int
    events: int
    finished_events: int
    championship_belts: int
    title_acquisitions: int


@dataclass(frozen=True)
class DataCenterOverviewResponse:
    counts: DataCenterCountsResponse
    recent_matches: list[MatchRowResponse] = field(default_factory=list)


@dataclass(frozen=True)
class WrestlerRowResponse:
    name: str
    brand: str | None
    real_name: str | None
    birth_date: str | None
    #: 실제 출생지.
    birth_place: str | None
    #: 방송이 부르는 연고지. `|`로 여럿일 수 있다.
    billed_from: str | None
    #: 둘이 다른가. **`None`은 한쪽이 없어 비교를 못 했다는 뜻**이고 "같다"가 아니다.
    hometown_differs: bool | None
    finisher: str | None
    stable_team: str | None
    matches: int
    wins: int
    losses: int
    win_rate: float | None
    titles: int


@dataclass(frozen=True)
class WrestlerPageResponse:
    items: list[WrestlerRowResponse]
    total: int
    page: int
    size: int
    brands: list[str]
    #: 소개 연고지가 실제와 **다른** 선수 수 (필터와 무관하게 전체 기준).
    #: 화면이 필터 칩에 이 수를 적는다.
    hometown_differs_total: int = 0


@dataclass(frozen=True)
class EventOptionResponse:
    slug: str
    label: str


@dataclass(frozen=True)
class MatchPageResponse:
    items: list[MatchRowResponse]
    total: int
    page: int
    size: int
    events: list[EventOptionResponse]


@dataclass(frozen=True)
class BeltStatResponse:
    belt_name: str
    reigns: int
    holders: int
    top_holder: str | None
    top_holder_reigns: int
    former_names: list[str]


@dataclass(frozen=True)
class ExcludedBeltResponse:
    belt_name: str
    reigns: int
    reason: str


@dataclass(frozen=True)
class HolderStatResponse:
    name: str
    reigns: int
    belts: int


@dataclass(frozen=True)
class ChampionshipStatsResponse:
    total_acquisitions: int
    belt_count: int
    holder_count: int
    belts: list[BeltStatResponse]
    top_holders: list[HolderStatResponse]
    excluded_belts: list[ExcludedBeltResponse]


@dataclass(frozen=True)
class BeltReignResponse:
    competitor_name: str
    belt_name: str
    won_at: str


@dataclass(frozen=True)
class BeltHolderResponse:
    name: str
    reigns: int
    history: list[BeltReignResponse]


@dataclass(frozen=True)
class BeltDetailResponse:
    belt_name: str
    former_names: list[str]
    reigns: int
    holder_count: int
    holders: list[BeltHolderResponse]


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


@dataclass(frozen=True)
class BrandCountResponse:
    brand: str
    wrestlers: int


@dataclass(frozen=True)
class RatedWrestlerResponse:
    name: str
    wins: int
    losses: int
    win_rate: float


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


@dataclass(frozen=True)
class BirthdayResponse:
    """다가오는 생일 한 건. `age`는 **그 생일에 맞이할** 나이다."""

    name: str
    #: 선수는 브랜드, 비선수는 CSV 구역(`Executives` 등).
    group: str | None
    #: `"wrestler"` | `"staff"`.
    kind: str
    #: 비선수만 있다 — `Commentator` 등.
    role: str | None
    #: `MM-DD`
    month_day: str
    birth_date: str
    age: int
    days_away: int


@dataclass(frozen=True)
class BirthdayBoardResponse:
    """생일 보드.

    `dated`/`total`을 함께 내보내는 이유는 **이 목록이 명부 전부가 아니기**
    때문이다 — 화면이 "207/245명 기준"이라고 적을 수 있어야 한다 (§14 분모 규칙).
    분모에는 선수와 비선수가 함께 들어간다.
    """

    today: str
    entries: list[BirthdayResponse] = field(default_factory=list)
    dated: int = 0
    total: int = 0
