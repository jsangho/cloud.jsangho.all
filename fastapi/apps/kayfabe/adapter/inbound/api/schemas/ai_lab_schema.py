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
    """저장된 출처 URL — 프롬프트에 넣은 청크의 **문서 주소**다. 어떤 청크가 어떤
    유사도로 쓰였는지는 지금 구조가 기록하지 않는다. 문서 단위 대조는 Phase 3-4가
    맡고(`GET /api/ai-lab/knowledge`), 유사도는 3-6에서 따로 다룬다."""


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


class RuleVerdictSchema(_Camel):
    """규칙 하나에 대한 판정 (Phase 3-6).

    `applicable=False`는 **통과가 아니다** — 잴 수 없었다는 뜻이고, 잴 수 없으면
    그 예측은 자격을 얻지 못한다.
    """

    code: str
    failed: bool
    applicable: bool
    detail: str
    """왜 그렇게 판정했는지. 사실만 적는다 — 화면이 문구를 지어내지 않게."""


class EvaluationItemSchema(_Camel):
    event_slug: str = Field(alias="eventSlug")
    event_label: str = Field(alias="eventLabel")
    match_key: str = Field(alias="matchKey")
    match_title: str = Field(alias="matchTitle")
    generated_at: datetime = Field(alias="generatedAt")
    result_recorded_at: datetime | None = Field(default=None, alias="resultRecordedAt")
    """결과가 **시스템에 기록된** 시각. 경기가 끝난 시각이 아니다."""
    status: str
    """"eligible" | "disqualified" | "held" | "pending" | "not_applicable"."""
    eligible: bool
    verdicts: list[RuleVerdictSchema]


class EvaluationRuleSchema(_Camel):
    code: str
    label: str
    severity: str
    """"exclude" | "disqualify" | "hold". **보류를 실격으로 적지 않기 위해 함께 낸다.**"""
    description: str
    blocked: int
    """이 규칙이 막은 예측 수."""


class EvaluationTotalsSchema(_Camel):
    """다섯 칸의 합이 `predictions`와 같다 — 어디로도 새지 않는다."""

    predictions: int
    fallback: int
    pending: int
    disqualified: int
    held: int
    """누수를 증명도 반증도 못 한 예측. **실격과 다른 상태다.**"""
    eligible: int


class EligiblePerformanceSchema(_Camel):
    """**자격 있는 표본이 있을 때만 존재한다.**"""

    sample: int
    correct: int
    incorrect: int
    accuracy: float
    accuracy_low: float = Field(alias="accuracyLow")
    accuracy_high: float = Field(alias="accuracyHigh")
    events_covered: int = Field(alias="eventsCovered")


class AiLabEvaluationSchema(_Camel):
    totals: EvaluationTotalsSchema
    integrity: IntegritySchema
    rules: list[EvaluationRuleSchema]
    items: list[EvaluationItemSchema]
    performance: EligiblePerformanceSchema | None = None
    """자격 있는 표본이 0건이면 `null`. **0%도 빈 객체도 아니다.**"""


class ReportContributionSchema(_Camel):
    """예측 하나에 실린 에이전트 한 명의 몫 (Phase 3-5)."""

    agent: str
    weight: float
    opinionated: bool
    """`pick`이 있었는가. **의견 없음은 오답이 아니다** — 동의도 분모에도 안 들어간다."""


class PerformanceItemSchema(_Camel):
    """예측 하나 + 그것을 만든 리포트 구성.

    **승률과 근거의 두께는 같지 않다.** 의견이 하나뿐이고 그 weight가 1.0이면
    분포가 붕괴해 `winProbability`가 1.0이 되므로, 화면은 `coverage`를 반드시
    함께 세워야 한다.
    """

    event_slug: str = Field(alias="eventSlug")
    event_label: str = Field(alias="eventLabel")
    match_key: str = Field(alias="matchKey")
    match_title: str = Field(alias="matchTitle")
    win_probability: float = Field(alias="winProbability")
    confidence: float
    """저장된 값. `agreement × coverage`가 이 값을 재현한다."""
    agreement: float | None = None
    """최종 pick에 동의한 의견 / 전체 의견. **의견이 없으면 `None`** — 0.0이 아니다."""
    coverage: float
    """의견 낸 에이전트 / 물어본 에이전트."""
    correct: bool | None = None
    """미채점이면 `None` — 실패(False)와 다른 상태다."""
    reports: list[ReportContributionSchema]


class ConsensusLevelSchema(_Camel):
    """`(answered, agreed)` 한 짝.

    **`confidence`로 묶지 않는다** — 곱이 같으면 "2명이 답해 둘 다 동의"와
    "3명이 답해 2명 동의"가 한 줄로 접히고, 근거의 두께 차이가 사라진다.
    """

    confidence: float
    answered: int
    agreed: int
    predictions: int
    graded: int
    """결과가 나온 예측 수 — **정답률의 분모다.**"""
    correct: int


class AgentContributionSchema(_Camel):
    """그 에이전트의 `weight`가 실제로 변하는가 (Phase 3-5).

    3-3의 정확도와 **다른 것을 잰다.** 한 값만 내는 에이전트는 100% 맞혀도 최종
    승률의 변동에는 기여하지 않는다.
    """

    agent: str
    reports: int
    opinions: int
    """`pick`이 있는 리포트 수 — 아래 값들의 분모다."""
    distinct_weights: int = Field(alias="distinctWeights")
    min_weight: float | None = Field(default=None, alias="minWeight")
    max_weight: float | None = Field(default=None, alias="maxWeight")
    constant: bool | None = None
    """값이 하나뿐인가. **의견이 없으면 `None`** — 상수라고 말할 근거가 없다."""


class PerformanceTotalsSchema(_Camel):
    predictions: int
    """저장된 예측 전체 (폴백 포함)."""
    graded: int
    correct: int
    incorrect: int
    bookmaker_fallback: int = Field(alias="bookmakerFallback")
    singles: int
    """폴백을 뺀 2파전 예측 수. 형식은 저장된 `pick` 인코딩에서 나온다."""
    multi: int


class InferentialSchema(_Camel):
    """추론 지표를 낼 수 있는 상태인가.

    **새 판정이 아니라 `integrity`의 투영이다** — 캘리브레이션·Brier 같은 지표는
    무결성 판정이 통과해야 의미가 생기고, 그 규칙을 화면마다 다시 쓰면 갈린다.
    """

    available: bool
    reasons: list[str]


class AiLabPerformanceSchema(_Camel):
    totals: PerformanceTotalsSchema
    integrity: IntegritySchema
    inferential: InferentialSchema
    consensus: list[ConsensusLevelSchema]
    contributions: list[AgentContributionSchema]
    items: list[PerformanceItemSchema]


class KnowledgeDocumentSchema(_Camel):
    """코퍼스 문서 한 건 (Phase 3-4).

    `usedByReports`는 **인용 주장이 아니라 적재 기록이다** — 저장된 출처가 실제로
    프롬프트에 넣은 청크의 URL이라서 셀 수 있는 값이다. 리포트당 최대 5건만 남으므로
    이 수치는 하한이다.
    """

    source_url: str = Field(alias="sourceUrl")
    source_domain: str = Field(alias="sourceDomain")
    title: str | None = None
    chunks: int
    chunks_embedded: int = Field(alias="chunksEmbedded")
    """임베딩이 없는 청크는 검색되지 않는다 — 있으나 마나 한 상태를 숨기지 않는다."""
    chunks_with_published_at: int = Field(alias="chunksWithPublishedAt")
    first_published_at: datetime | None = Field(default=None, alias="firstPublishedAt")
    last_collected_at: datetime | None = Field(default=None, alias="lastCollectedAt")
    used_by_reports: int = Field(alias="usedByReports")
    used_by_agents: list[str] = Field(alias="usedByAgents")


class KnowledgeDomainSchema(_Camel):
    domain: str
    documents: int
    chunks: int
    used_documents: int = Field(alias="usedDocuments")


class KnowledgeTotalsSchema(_Camel):
    documents: int
    chunks: int
    chunks_embedded: int = Field(alias="chunksEmbedded")
    chunks_with_published_at: int = Field(alias="chunksWithPublishedAt")
    domains: int
    last_collected_at: datetime | None = Field(default=None, alias="lastCollectedAt")
    used_documents: int = Field(alias="usedDocuments")
    """프롬프트에 한 번이라도 들어간 문서. **하한이다** — 출처는 리포트당 5건까지만 남는다."""
    used_document_rate: float | None = Field(default=None, alias="usedDocumentRate")
    """문서가 0건이면 `None` — 0이 아니다."""
    reports_total: int = Field(alias="reportsTotal")
    reports_with_sources: int = Field(alias="reportsWithSources")
    sources_outside_corpus: int = Field(alias="sourcesOutsideCorpus")
    """리포트가 든 출처 중 지금 코퍼스에 없는 URL 수. 재수집·삭제로 생긴다."""


class AiLabKnowledgeSchema(_Camel):
    totals: KnowledgeTotalsSchema
    integrity: IntegritySchema
    documents: list[KnowledgeDocumentSchema]
    domains: list[KnowledgeDomainSchema]


class AiLabPredictionsSchema(_Camel):
    """예측 목록 + 그 목록을 어떻게 읽어야 하는지(무결성).

    **둘을 한 응답에 담는다.** 화면이 목록만 받아 적중률을 자랑하지 못하게 하려는
    것이고, 무결성 수치를 두 번 계산하지 않게 하려는 것이다(Phase 3-0 재사용).
    """

    totals: PredictionTotalsSchema
    integrity: IntegritySchema
    events: list[PredictionEventSchema]
    items: list[PredictionItemSchema]
