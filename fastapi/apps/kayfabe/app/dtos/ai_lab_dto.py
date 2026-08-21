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

from kayfabe.app.services.ai_lab_integrity import (
    AgentActivity,
    IntegrityFacts,
    PredictionTotals,
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
