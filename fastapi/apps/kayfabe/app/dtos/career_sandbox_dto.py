"""커리어 샌드박스 응답 DTO. **근거를 함께 내보낸다.**

`match_sim` 쪽 장난감이 입력을 그대로 돌려주는 것과 같은 이유다 — 숫자만 주면
화면이 그것을 설명할 수 없고, 설명 없는 수치는 진짜처럼 읽힌다.

특히 은퇴 위험은 **밴드와 근거만** 내보내고 점수를 내보내지 않는다. 사용자 요구
§6 — "정확한 위험 수치가 검증되지 않았다면 근거 없는 퍼센트를 표시하지 말고
'안정', '주의', '높은 위험' 등 설명 가능한 단계로 제공한다." 가중합을 퍼센트로
적으면 검증되지 않은 정밀도가 생긴다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class AbilityDto:
    in_ring: int
    mic: int
    stamina: int
    resilience: int


@dataclass(frozen=True)
class RiskDto:
    """은퇴 위험. **점수 칸이 없다 — 일부러 없다.**"""

    band: str
    #: 왜 그 밴드인지. 무게 순으로 정렬돼 있다.
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class InjuryDto:
    kind: str
    severity: str
    season: int
    week: int
    weeks_out: int
    recovered: bool
    recurrence: bool
    permanent: bool


@dataclass(frozen=True)
class RetirementDto:
    cause: str
    season: int
    week: int
    age: int
    wins: int
    losses: int
    held: tuple[str, ...]
    reigns: int
    titles: tuple[str, ...]
    note: str


@dataclass(frozen=True)
class IntentDto:
    origin: str
    cause: str
    season: int
    week: int
    final_season: bool


@dataclass(frozen=True)
class WrestlerDto:
    name: str
    style: str
    brand: str
    age: int
    debut_age: int
    alignment: str
    popularity: int
    ability: AbilityDto
    condition: int
    status: str
    wins: int
    losses: int
    reigns: tuple[str, ...]
    held: tuple[str, ...]
    out_weeks: int
    is_player: bool
    injuries: tuple[InjuryDto, ...] = ()
    #: 최근 능력치 변화. 시즌이 둘 미만이면 `None`.
    trend: AbilityDto | None = None
    intent: IntentDto | None = None
    retirement: RetirementDto | None = None
    risk: RiskDto | None = None


@dataclass(frozen=True)
class RelationshipDto:
    a: str
    b: str
    kind: str
    heat: int
    started_week: int
    last_week: int
    history: tuple[str, ...] = ()
    #: **끓는 라이벌인가** (`career_relations.is_feud`). `kind` 만으로는 못 센다 —
    #: 경기마다 진 쪽이 라이벌 kind 를 갖기 때문이다. 임계값은 서버에 둔다:
    #: 화면이 60을 박아 두면 설정을 바꿨을 때 화면만 거짓말을 한다.
    feud: bool = False


@dataclass(frozen=True)
class TitleDto:
    name: str
    brand: str
    required_popularity: int
    holder: str | None
    defenses: int
    #: 재위 주차. 보유 중이 아니면 `None`.
    reign_weeks: int | None = None


@dataclass(frozen=True)
class ChoiceDto:
    code: str
    label: str
    enabled: bool
    note: str


@dataclass(frozen=True)
class EventDto:
    id: str
    kind: str
    season: int
    week: int
    subject: str
    other: str | None
    headline: str
    detail: str
    choices: tuple[ChoiceDto, ...]


@dataclass(frozen=True)
class LogDto:
    season: int
    week: int
    kind: str
    subject: str
    summary: str
    other: str | None = None
    result: str | None = None
    title: str | None = None


@dataclass(frozen=True)
class SeasonSummaryDto:
    season: int
    wins: int
    losses: int
    age: int
    ability: AbilityDto
    ability_delta: AbilityDto
    titles_won: tuple[str, ...]
    defenses: int
    injuries: int
    retired: tuple[str, ...]
    highlights: tuple[str, ...]
    risk_band: str


@dataclass(frozen=True)
class CardDto:
    """다음 경기. 없으면 `kind == "rest"`."""

    kind: str
    opponent: str | None = None
    title: str | None = None
    partner: str | None = None
    opponents: tuple[str, ...] = ()
    note: str = ""


@dataclass(frozen=True)
class WeekReportDto:
    season: int
    week: int
    kind: str
    opponent: str | None = None
    won: bool | None = None
    title: str | None = None
    title_changed: bool = False
    finish: str | None = None
    rating: int = 0
    popularity_delta: int = 0
    injured: str | None = None
    injured_weeks: int = 0
    promoted_to: str | None = None
    opened_events: tuple[str, ...] = ()
    retired: bool = False
    risk_band: str = ""
    probability: float = 0.0


@dataclass(frozen=True)
class CareerSummaryDto:
    """목록 한 줄."""

    id: int
    player_name: str
    season: int
    week: int
    season_weeks: int
    phase: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class CareerViewDto:
    """대시보드 한 장. **화면이 필요한 것을 한 번에 준다.**

    요청을 여섯 번 보내게 만들면 화면이 조각마다 다른 시점의 상태를 섞어 그린다 —
    주차 진행 직후가 특히 그렇다.
    """

    id: int
    season: int
    week: int
    #: 시즌 길이. **화면이 `19 / 52` 를 서버 값으로 적는다** — 52를 프론트에
    #: 박아 두면 설정을 바꿔도 화면만 거짓말을 한다.
    season_weeks: int
    phase: str
    action_points: int
    max_action_points: int
    player: WrestlerDto
    next_card: CardDto
    pending: tuple[EventDto, ...] = ()
    titles: tuple[TitleDto, ...] = ()
    relationships: tuple[RelationshipDto, ...] = ()
    roster: tuple[WrestlerDto, ...] = ()
    seasons: tuple[SeasonSummaryDto, ...] = ()
    recent_log: tuple[LogDto, ...] = ()
    #: 마지막 주차 진행의 보고. 새로 만든 커리어면 `None`.
    last_report: WeekReportDto | None = None


@dataclass(frozen=True)
class CareerOutcome:
    """쓰기 한 번의 결과. **둘 중 하나만 채워진다.**

    왜 둘인가: 중복 요청에는 **최초 요청의 응답 본문을 그대로** 돌려줘야 한다
    (사용자 요구 §B-2). 그 본문은 영수증에 dict 로 들어 있고, 다시 `CareerViewDto`
    로 조립하려면 중첩 데이터클래스 열다섯 개를 되살리는 역직렬화기가 필요하다 —
    DTO 모양을 두 곳에서 관리하게 되는 길이다.

    그래서 재시도 경로는 dict 를 그대로 올려 보낸다. 응답 모델이
    `populate_by_name=True` 라 snake_case dict 를 그대로 먹고, 나올 때 camelCase
    로 붙는다. **저장된 본문이 응답 스키마 검증을 다시 거친다**는 부수 효과도
    있다 — 저장된 blob 을 믿지 않는다.
    """

    view: CareerViewDto | None = None
    #: 영수증에 저장된 응답 본문(snake_case). 재시도일 때만 찬다.
    replayed: dict[str, Any] | None = None

    @property
    def body(self) -> CareerViewDto | dict[str, Any]:
        """라우터가 그대로 반환하는 값."""
        if self.replayed is not None:
            return self.replayed
        if self.view is None:  # pragma: no cover - 생성자가 둘 중 하나를 보장한다
            raise ValueError("CareerOutcome 이 비어 있습니다")
        return self.view
