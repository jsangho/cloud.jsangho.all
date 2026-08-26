"""AI LAB DTO — 유스케이스가 주고받는 값 (Phase 3-0·3-1).

**Pydantic 스키마를 import하지 않는다.** 여기서 `to_schema()`를 들고 있으면 app 레이어가
adapter를 향하게 되어 의존성이 바깥으로 뒤집힌다(CLAUDE.md §0-2). 매핑은 인접한
`ai_prediction_router._to_schema()`와 같은 자리 — 라우터가 한다.

실제로 그 방향이 문제를 일으킨다: `dto → schema`는 `kayfabe.adapter.inbound.api`
패키지 `__init__`을 깨워 라우터들을 줄줄이 import하고, 그 라우터가 다시 이 모듈을
찾으면서 순환이 된다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from kayfabe.app.services.ai_lab_evaluation import (
    EligiblePerformance,
    EvaluationItem,
    EvaluationTotals,
    RuleTally,
)
from kayfabe.app.services.ai_lab_integrity import (
    AgentActivity,
    AgentAnalysis,
    AgentAnalysisTotals,
    IntegrityFacts,
    PredictionTotals,
)
from kayfabe.app.services.ai_lab_knowledge import (
    DomainFacts,
    KnowledgeDocument,
    KnowledgeTotals,
)
from kayfabe.app.services.ai_lab_performance import (
    AgentContribution,
    ConsensusLevel,
    PerformanceItem,
    PerformanceTotals,
)


@dataclass(frozen=True)
class SystemComponent:
    """시스템 구성요소 하나의 실측 상태."""

    key: str
    label: str
    #: "operational" | "degraded" | "empty" | "unknown"
    state: str
    detail: str


@dataclass(frozen=True)
class RecentPrediction:
    event_slug: str
    event_label: str
    match_key: str
    match_title: str
    pick_name: str
    win_probability: float
    confidence: float
    source: str
    generated_at: datetime
    winner_name: str | None
    #: 아직 안 끝난 경기면 `None` — 실패(False)와 다른 상태다.
    correct: bool | None


@dataclass(frozen=True)
class AiLabOverviewResponse:
    predictions: PredictionTotals
    integrity: IntegrityFacts
    system: list[SystemComponent]
    agents: list[AgentActivity]
    recent: list[RecentPrediction]


@dataclass(frozen=True)
class AgentReportItem:
    """저장된 에이전트 의견 그대로. `pick`이 `None`이면 의견 없음이다."""

    agent: str
    pick: str | None
    weight: float
    summary: str
    sources: tuple[str, ...]


@dataclass(frozen=True)
class PredictionItem:
    event_slug: str
    event_label: str
    match_key: str
    match_title: str
    pick: str
    pick_name: str
    win_probability: float
    confidence: float
    rationale: str
    source: str
    generated_at: datetime
    winner_name: str | None
    #: 결과가 아직 없으면 `None` (Pending).
    correct: bool | None
    reports: tuple[AgentReportItem, ...]


@dataclass(frozen=True)
class PredictionEvent:
    slug: str
    label: str
    count: int


@dataclass(frozen=True)
class AiLabPredictionsResponse:
    totals: PredictionTotals
    integrity: IntegrityFacts
    events: list[PredictionEvent]
    items: list[PredictionItem]


@dataclass(frozen=True)
class AiLabEvaluationResponse:
    """어떤 예측이 채점 대상이 될 자격이 있는가 (Phase 3-6).

    **성능을 재는 응답이 아니다.** `performance`는 자격 있는 표본이 있을 때만
    만들어지고, 0건이면 `None`이다 — 0%도 빈 객체도 아니다.

    무결성을 같은 응답에 담는 이유는 다른 화면과 같다. 다만 여기서는 관계가 뒤집힌다 —
    3-0의 경고가 이 판정의 **결과**를 설명하는 것이 아니라, 이 판정이 그 경고의
    **원인**을 예측 단위로 짚는다.
    """

    totals: EvaluationTotals
    integrity: IntegrityFacts
    rules: list[RuleTally]
    items: list[EvaluationItem]
    #: 자격 있는 표본이 없으면 `None`. **반드시 `None`이다.**
    performance: EligiblePerformance | None


@dataclass(frozen=True)
class InferentialAvailability:
    """추론 지표를 낼 수 있는 상태인가 (Phase 3-5).

    **새 판정이 아니라 `IntegrityFacts`의 투영이다.** 캘리브레이션·Brier 같은 추론
    지표는 무결성 판정이 통과해야 의미가 생기는데, 그 판정 규칙을 화면마다 다시
    쓰면 갈린다. 여기서는 3-0이 이미 내린 결론을 이 화면의 언어로 옮기기만 한다.
    """

    available: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class AiLabPerformanceResponse:
    """최종 승률이 무엇으로 만들어졌는지 (Phase 3-5).

    **정확도를 재는 응답이 아니다.** 전체 적중률은 3-1이, 에이전트별 정확도는 3-3이
    이미 낸다. 여기 실린 `correct`·`graded`는 그 숫자를 다시 세우기 위한 것이 아니라
    각 합의 층의 **분모를 밝히기 위한** 것이다.
    """

    totals: PerformanceTotals
    integrity: IntegrityFacts
    inferential: InferentialAvailability
    consensus: list[ConsensusLevel]
    contributions: list[AgentContribution]
    items: list[PerformanceItem]


@dataclass(frozen=True)
class AiLabKnowledgeResponse:
    """코퍼스에 무엇이 있고 그중 무엇이 쓰였는지 (Phase 3-4).

    무결성을 같은 응답에 담는 이유가 다른 화면보다 여기서 더 직접적이다 — 발행일이
    0건이라 시간 검증이 불가능하다는 판정의 **원인이 바로 이 코퍼스**다.
    """

    totals: KnowledgeTotals
    integrity: IntegrityFacts
    documents: list[KnowledgeDocument]
    domains: list[DomainFacts]


@dataclass(frozen=True)
class AiLabAgentsResponse:
    """에이전트 성적 + 그 성적을 어떻게 읽어야 하는지 (Phase 3-3).

    무결성을 같은 응답에 담는 이유는 예측 목록과 같다 — 정확도만 따로 받아 가면
    화면이 맥락 없이 세울 수 있고, 같은 판정을 두 번 계산하게 된다.
    """

    totals: AgentAnalysisTotals
    integrity: IntegrityFacts
    agents: list[AgentAnalysis]
