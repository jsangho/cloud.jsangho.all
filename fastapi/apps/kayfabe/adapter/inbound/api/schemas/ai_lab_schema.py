"""AI LAB 응답 스키마 — Phase 3-0·3-1.

**모든 수치는 DB에서 센 값이다.** 없는 값은 `None`으로 나가고 화면이 그 칸을 비운다.
적중률은 점추정만 내보내지 않고 **신뢰구간을 함께** 내보낸다 — 표본 12건의 100%를
숫자 하나로 보내면 화면이 무슨 짓을 해도 과장이 된다.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class _Camel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class PredictionTotalsSchema(_Camel):
    total: int
    """저장된 예측 전체 (북메이커 폴백 포함)."""
    graded: int
    """실제 결과가 나와 채점된 예측. **폴백은 빠진다.**"""
    correct: int
    incorrect: int
    hit_rate: float | None = Field(default=None, alias="hitRate")
    """0.0~1.0. 채점된 예측이 없으면 `None` — 0이 아니다."""
    hit_rate_low: float | None = Field(default=None, alias="hitRateLow")
    """윌슨 95% 신뢰구간 하한. **화면은 이 값을 함께 적어야 한다.**"""
    hit_rate_high: float | None = Field(default=None, alias="hitRateHigh")
    avg_confidence: float | None = Field(default=None, alias="avgConfidence")
    avg_win_probability: float | None = Field(default=None, alias="avgWinProbability")
    bookmaker_fallback: int = Field(alias="bookmakerFallback")


class IntegritySchema(_Camel):
    """적중률을 믿어도 되는지에 대한 실측. 판정과 **근거**를 함께 낸다."""

    sample_size: int = Field(alias="sampleSize")
    events_covered: int = Field(alias="eventsCovered")
    events_total: int = Field(alias="eventsTotal")
    self_referencing_predictions: int = Field(alias="selfReferencingPredictions")
    """그 대회 자체를 다룬 문서를 근거로 인용한 예측 수."""
    predictions_with_sources: int = Field(alias="predictionsWithSources")
    chunks_total: int = Field(alias="chunksTotal")
    chunks_with_published_at: int = Field(alias="chunksWithPublishedAt")
    temporal_verifiable: bool = Field(alias="temporalVerifiable")
    """발행일이 하나도 없으면 `False` — 누수가 없다는 것을 증명할 수 없다."""
    generalizable: bool
    reasons: list[str]


class SystemComponentSchema(_Camel):
    key: str
    label: str
    state: str
    """"operational" | "degraded" | "empty" | "unknown". **가짜 초록불을 만들지 않는다.**"""
    detail: str


class AgentActivitySchema(_Camel):
    agent: str
    """코드의 이름 그대로 — storyline · odds · rumor."""
    reports: int
    with_pick: int = Field(alias="withPick")
    opinion_rate: float | None = Field(default=None, alias="opinionRate")
    avg_weight: float | None = Field(default=None, alias="avgWeight")


class RecentPredictionSchema(_Camel):
    event_slug: str = Field(alias="eventSlug")
    event_label: str = Field(alias="eventLabel")
    match_key: str = Field(alias="matchKey")
    match_title: str = Field(alias="matchTitle")
    pick_name: str = Field(alias="pickName")
    win_probability: float = Field(alias="winProbability")
    confidence: float
    source: str
    generated_at: datetime = Field(alias="generatedAt")
    winner_name: str | None = Field(default=None, alias="winnerName")
    correct: bool | None = None
    """아직 안 끝난 경기면 `None` — 미채점과 실패는 다른 상태다."""


class AiLabOverviewSchema(_Camel):
    predictions: PredictionTotalsSchema
    integrity: IntegritySchema
    system: list[SystemComponentSchema]
    agents: list[AgentActivitySchema]
    recent: list[RecentPredictionSchema]


class AgentReportSchema(_Camel):
    """에이전트 한 명의 의견. 저장된 값을 그대로 옮긴다 — 추정하지 않는다.

    필드 이름은 기존 `/api/ple_events/{slug}/ai-predictions`의 리포트와 같다.
    화면이 같은 `AiReportDialog`를 그대로 열 수 있어야 하기 때문이다.
    """

    agent: str
    pick: str | None = None
    """`None`이면 **의견 없음**이다 — 빈 문자열과 구분한다."""
    weight: float
    summary: str
    sources: list[str]
    """저장된 출처 URL. **검색된 청크가 아니다** — 어떤 청크가 쓰였는지는 지금 구조가
    기록하지 않으므로 그렇게 주장할 수 없다(Phase 3-4·3-6에서 따로 다룬다)."""


class PredictionItemSchema(_Camel):
    event_slug: str = Field(alias="eventSlug")
    event_label: str = Field(alias="eventLabel")
    match_key: str = Field(alias="matchKey")
    match_title: str = Field(alias="matchTitle")
    pick: str
    pick_name: str = Field(alias="pickName")
    win_probability: float = Field(alias="winProbability")
    confidence: float
    rationale: str
    source: str
    """"agents" | "bookmaker_fallback" — 폴백으로 만들어졌는지 화면이 구분해야 한다."""
    generated_at: datetime = Field(alias="generatedAt")
    winner_name: str | None = Field(default=None, alias="winnerName")
    correct: bool | None = None
    """결과가 아직 없으면 `None` (Pending) — 실패(False)와 다른 상태다."""
    reports: list[AgentReportSchema]


class PredictionEventSchema(_Camel):
    """예측이 **실제로 존재하는** 대회만. 필터 목록을 화면에 박지 않는다."""

    slug: str
    label: str
    count: int


class AgentAnalysisSchema(_Camel):
    """에이전트 한 명의 성적 (Phase 3-3).

    **분모를 함께 낸다.** 비율만 보내면 화면이 "90%"만 세울 수 있고, 그 뒤의 9/10이
    사라진다. 표본이 5~10건인 지금은 분모가 비율보다 중요하다.
    """

    agent: str
    """코드의 이름 그대로 — storyline · odds · rumor."""
    reports: int
    with_pick: int = Field(alias="withPick")
    no_opinion: int = Field(alias="noOpinion")
    response_rate: float | None = Field(default=None, alias="responseRate")
    """리포트 수 / 전체 예측 수."""
    opinion_rate: float | None = Field(default=None, alias="opinionRate")
    gradable: int
    """의견을 냈고 결과도 나온 리포트 — **정확도의 분모다.**"""
    correct: int
    incorrect: int
    accuracy: float | None = None
    """채점 대상이 없으면 `None` — 0.0이 아니다."""
    accuracy_low: float | None = Field(default=None, alias="accuracyLow")
    """윌슨 95% 신뢰구간. **화면은 이 값을 함께 적어야 한다.**"""
    accuracy_high: float | None = Field(default=None, alias="accuracyHigh")
    avg_weight: float | None = Field(default=None, alias="avgWeight")
    avg_weight_opinionated: float | None = Field(
        default=None, alias="avgWeightOpinionated"
    )
    matches_covered: int = Field(alias="matchesCovered")
    events_covered: int = Field(alias="eventsCovered")
    self_referencing_reports: int = Field(alias="selfReferencingReports")
    """그 대회 자체를 다룬 문서를 인용한 리포트 수."""
    uses_knowledge: bool = Field(alias="usesKnowledge")
    """출처를 한 번이라도 낸 적이 있는가. 실측이다 — 코드를 읽어 정하지 않는다."""


class AgentTotalsSchema(_Camel):
    agent_count: int = Field(alias="agentCount")
    total_reports: int = Field(alias="totalReports")
    opinionated: int
    no_opinion: int = Field(alias="noOpinion")
    overall_opinion_rate: float | None = Field(default=None, alias="overallOpinionRate")
    gradable_reports: int = Field(alias="gradableReports")
    total_predictions: int = Field(alias="totalPredictions")
    """응답률의 분모 — 폴백을 뺀 예측 수."""


class AiLabAgentsSchema(_Camel):
    totals: AgentTotalsSchema
    integrity: IntegritySchema
    agents: list[AgentAnalysisSchema]


class AiLabPredictionsSchema(_Camel):
    """예측 목록 + 그 목록을 어떻게 읽어야 하는지(무결성).

    **둘을 한 응답에 담는다.** 화면이 목록만 받아 적중률을 자랑하지 못하게 하려는
    것이고, 무결성 수치를 두 번 계산하지 않게 하려는 것이다(Phase 3-0 재사용).
    """

    totals: PredictionTotalsSchema
    integrity: IntegritySchema
    events: list[PredictionEventSchema]
    items: list[PredictionItemSchema]
