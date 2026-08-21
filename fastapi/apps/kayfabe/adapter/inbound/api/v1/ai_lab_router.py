"""AI LAB 라우터 (Phase 3-0·3-1).

**LLM을 부르지 않는다.** 저장된 예측·리포트·지식 청크를 읽어 집계할 뿐이라, 화면
진입이 비용을 만들지 않는다(하네스 §3-D1). 예측 생성은 관리자 전용
`POST /api/ple_events/{slug}/ai-predictions`와 배치 스크립트의 몫이다.

DTO → 스키마 매핑은 인접한 `ai_prediction_router`와 같이 **여기서** 한다 — app 레이어가
Pydantic을 모르게 두기 위해서다(CLAUDE.md §0-2).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from kayfabe.adapter.inbound.api.schemas.ai_lab_schema import (
    AgentActivitySchema,
    AiLabOverviewSchema,
    IntegritySchema,
    PredictionTotalsSchema,
    RecentPredictionSchema,
    SystemComponentSchema,
)
from kayfabe.app.dtos.ai_lab_dto import AiLabOverviewResponse
from kayfabe.app.ports.input.ai_lab_use_case import AiLabUseCase
from kayfabe.dependencies.ai_lab_provider import get_ai_lab

logger = logging.getLogger("uvicorn.error")

ai_lab_router = APIRouter(prefix="/ai-lab", tags=["ai-lab"])


@ai_lab_router.get(
    "/overview",
    response_model=AiLabOverviewSchema,
    response_model_by_alias=True,
)
async def get_ai_lab_overview(use_case: AiLabUseCase = Depends(get_ai_lab)):
    """예측 집계·평가 신뢰성·시스템 상태·에이전트 활동·최근 예측.

    적중률은 점추정과 **윌슨 95% 신뢰구간**을 함께 준다 — 표본이 작을 때 점추정만
    보내면 화면이 무엇을 하든 과장이 된다.
    """
    logger.info("[AiLabRouter] get_ai_lab_overview")
    return to_schema(await use_case.get_overview())


def to_schema(response: AiLabOverviewResponse) -> AiLabOverviewSchema:
    return AiLabOverviewSchema(
        predictions=PredictionTotalsSchema(
            total=response.predictions.total,
            graded=response.predictions.graded,
            correct=response.predictions.correct,
            incorrect=response.predictions.incorrect,
            hit_rate=response.predictions.hit_rate,
            hit_rate_low=response.predictions.hit_rate_low,
            hit_rate_high=response.predictions.hit_rate_high,
            avg_confidence=response.predictions.avg_confidence,
            avg_win_probability=response.predictions.avg_win_probability,
            bookmaker_fallback=response.predictions.bookmaker_fallback,
        ),
        integrity=IntegritySchema(
            sample_size=response.integrity.sample_size,
            events_covered=response.integrity.events_covered,
            events_total=response.integrity.events_total,
            self_referencing_predictions=response.integrity.self_referencing_predictions,
            predictions_with_sources=response.integrity.predictions_with_sources,
            chunks_total=response.integrity.chunks_total,
            chunks_with_published_at=response.integrity.chunks_with_published_at,
            temporal_verifiable=response.integrity.temporal_verifiable,
            generalizable=response.integrity.generalizable,
            reasons=list(response.integrity.reasons),
        ),
        system=[
            SystemComponentSchema(
                key=item.key, label=item.label, state=item.state, detail=item.detail
            )
            for item in response.system
        ],
        agents=[
            AgentActivitySchema(
                agent=item.agent,
                reports=item.reports,
                with_pick=item.with_pick,
                opinion_rate=item.opinion_rate,
                avg_weight=item.avg_weight,
            )
            for item in response.agents
        ],
        recent=[
            RecentPredictionSchema(
                event_slug=item.event_slug,
                event_label=item.event_label,
                match_key=item.match_key,
                match_title=item.match_title,
                pick_name=item.pick_name,
                win_probability=item.win_probability,
                confidence=item.confidence,
                source=item.source,
                generated_at=item.generated_at,
                winner_name=item.winner_name,
                correct=item.correct,
            )
            for item in response.recent
        ],
    )
