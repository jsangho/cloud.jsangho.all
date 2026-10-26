"""커리어 샌드박스 스키마. camelCase 로 내보낸다(프로젝트 관례).

**은퇴 위험에 점수 칸이 없다.** `band` 와 `reasons` 뿐이다 — 사용자 요구 §6 가
"근거 없는 퍼센트를 표시하지 말고 설명 가능한 단계로" 라고 적었고, 가중합을
퍼센트로 내보내면 화면이 그걸 확률처럼 적는다. 칸을 안 만드는 것이 가장 확실한
방어다.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class _Camel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class AbilitySchema(_Camel):
    in_ring: int = Field(alias="inRing")
    mic: int
    stamina: int
    resilience: int


class RiskSchema(_Camel):
    """**점수 칸이 없다 — 일부러 없다.** 위 모듈 독스트링 참조."""

    band: str
    reasons: list[str] = Field(default_factory=list)


class InjurySchema(_Camel):
    kind: str
    severity: str
    season: int
    week: int
    weeks_out: int = Field(alias="weeksOut")
    recovered: bool
    recurrence: bool
    permanent: bool


class RetirementSchema(_Camel):
    cause: str
    season: int
    week: int
    age: int
    wins: int
    losses: int
    held: list[str] = Field(default_factory=list)
    reigns: int = 0
    titles: list[str] = Field(default_factory=list)
    note: str = ""


class IntentSchema(_Camel):
    """은퇴 **의사**. `RetirementSchema` 와 다른 칸이다 — 확정이 아니다."""

    origin: str
    cause: str
    season: int
    week: int
    final_season: bool = Field(alias="finalSeason")


class WrestlerSchema(_Camel):
    name: str
    style: str
    brand: str
    age: int
    debut_age: int = Field(alias="debutAge")
    alignment: str
    popularity: int
    ability: AbilitySchema
    condition: int
    status: str
    wins: int
    losses: int
    reigns: list[str] = Field(default_factory=list)
    held: list[str] = Field(default_factory=list)
    out_weeks: int = Field(default=0, alias="outWeeks")
    is_player: bool = Field(default=False, alias="isPlayer")
    injuries: list[InjurySchema] = Field(default_factory=list)
    trend: AbilitySchema | None = None
    intent: IntentSchema | None = None
    retirement: RetirementSchema | None = None
    risk: RiskSchema | None = None


class RelationshipSchema(_Camel):
    a: str
    b: str
    kind: str
    heat: int
    started_week: int = Field(alias="startedWeek")
    last_week: int = Field(alias="lastWeek")
    history: list[str] = Field(default_factory=list)
    #: 끓는 라이벌 여부. **임계값은 내보내지 않는다** — 판정만 보낸다. 화면이 수치를
    #: 받으면 거기서 자기 기준을 만들어 서버와 다른 라이벌 집합을 그린다.
    feud: bool = False


class TitleSchema(_Camel):
    name: str
    brand: str
    required_popularity: int = Field(alias="requiredPopularity")
    holder: str | None = None
    defenses: int = 0
    reign_weeks: int | None = Field(default=None, alias="reignWeeks")


class ChoiceSchema(_Camel):
    code: str
    label: str
    #: **못 고르는 선택지도 내려보낸다.** 지우면 화면이 왜 못 고르는지 말할 수 없다.
    enabled: bool = True
    note: str = ""


class EventSchema(_Camel):
    id: str
    kind: str
    season: int
    week: int
    subject: str
    other: str | None = None
    headline: str = ""
    detail: str = ""
    choices: list[ChoiceSchema] = Field(default_factory=list)


class LogSchema(_Camel):
    season: int
    week: int
    kind: str
    subject: str
    summary: str = ""
    other: str | None = None
    result: str | None = None
    title: str | None = None


class SeasonSummarySchema(_Camel):
    season: int
    wins: int
    losses: int
    age: int
    ability: AbilitySchema
    ability_delta: AbilitySchema = Field(alias="abilityDelta")
    titles_won: list[str] = Field(default_factory=list, alias="titlesWon")
    defenses: int = 0
    injuries: int = 0
    retired: list[str] = Field(default_factory=list)
    highlights: list[str] = Field(default_factory=list)
    risk_band: str = Field(default="", alias="riskBand")


class CardSchema(_Camel):
    kind: str
    opponent: str | None = None
    title: str | None = None
    partner: str | None = None
    opponents: list[str] = Field(default_factory=list)
    note: str = ""


class WeekReportSchema(_Camel):
    season: int
    week: int
    kind: str
    opponent: str | None = None
    won: bool | None = None
    title: str | None = None
    title_changed: bool = Field(default=False, alias="titleChanged")
    finish: str | None = None
    rating: int = 0
    popularity_delta: int = Field(default=0, alias="popularityDelta")
    injured: str | None = None
    injured_weeks: int = Field(default=0, alias="injuredWeeks")
    promoted_to: str | None = Field(default=None, alias="promotedTo")
    opened_events: list[str] = Field(default_factory=list, alias="openedEvents")
    retired: bool = False
    risk_band: str = Field(default="", alias="riskBand")
    probability: float = 0.0


class CareerSummarySchema(_Camel):
    id: int
    player_name: str = Field(alias="playerName")
    season: int
    week: int
    season_weeks: int = Field(alias="seasonWeeks")
    phase: str
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class CareerViewSchema(_Camel):
    """대시보드 한 장.

    `seasonWeeks` 를 내보내는 것이 중요하다 — 화면이 `19 / 52` 를 **서버 값으로**
    적어야 한다. 52를 프론트에 박아 두면 설정을 바꿨을 때 화면만 거짓말을 한다
    (사용자 요구 §1 — "단순히 화면에 표시되는 숫자만 변경하지 않는다").
    """

    id: int
    season: int
    week: int
    season_weeks: int = Field(alias="seasonWeeks")
    phase: str
    action_points: int = Field(alias="actionPoints")
    max_action_points: int = Field(alias="maxActionPoints")
    player: WrestlerSchema
    next_card: CardSchema = Field(alias="nextCard")
    pending: list[EventSchema] = Field(default_factory=list)
    titles: list[TitleSchema] = Field(default_factory=list)
    relationships: list[RelationshipSchema] = Field(default_factory=list)
    roster: list[WrestlerSchema] = Field(default_factory=list)
    seasons: list[SeasonSummarySchema] = Field(default_factory=list)
    recent_log: list[LogSchema] = Field(default_factory=list, alias="recentLog")
    last_report: WeekReportSchema | None = Field(default=None, alias="lastReport")


# ── 요청 ──────────────────────────────────────────────────────────

#: 쓰기 요청의 멱등 키 형식. 헤더 `Idempotency-Key` 로 온다(본문이 아니다 —
#: 이유는 `career_sandbox_router` 모듈 독스트링).
#:
#: **길이 하한이 8인 것은 의도다.** `"1"` 같은 키를 받으면 서로 다른 사용자 의도가
#: 같은 키를 쓰기 쉽고, 그러면 멱등성이 "앞 요청의 응답을 돌려주는" 버그가 된다.
#: 화면은 `crypto.randomUUID()`(36자)를 쓴다.
#:
#: 문자 집합을 좁히는 것은 로그·URL 에 그대로 실려도 안전하게 하려는 것이다.
REQUEST_KEY_MIN = 8
REQUEST_KEY_MAX = 64
REQUEST_KEY_PATTERN = r"^[A-Za-z0-9_-]+$"


class CreateCareerRequest(_Camel):
    name: str = Field(min_length=1, max_length=40)
    style: str
    #: 데뷔 나이. 범위는 서버가 다시 검증한다(`Balance`).
    age: int = Field(default=24, ge=18, le=40)
    #: 주면 결과가 재현된다. 안 주면 서버가 만든다.
    seed: int | None = Field(default=None, ge=0, le=2**31 - 1)


class ActionRequest(_Camel):
    #: `훈련` · `프로모` · `휴식` · `관계` · `협상`.
    action: str
    #: 훈련이면 능력치 이름, 관계면 상대 선수 이름.
    target: str | None = None


class ResolveRequest(_Camel):
    choice: str = Field(min_length=1, max_length=40)
