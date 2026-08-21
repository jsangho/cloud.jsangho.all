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
