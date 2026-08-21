"""AI LAB 라우터 (Phase 3-0·3-1).

**LLM을 부르지 않는다.** 저장된 예측·리포트·지식 청크를 읽어 집계할 뿐이라, 화면
진입이 비용을 만들지 않는다(하네스 §3-D1). 예측 생성은 관리자 전용
`POST /api/ple_events/{slug}/ai-predictions`와 배치 스크립트의 몫이다.

DTO → 스키마 매핑은 인접한 `ai_prediction_router`와 같이 **여기서** 한다 — app 레이어가
Pydantic을 모르게 두기 위해서다(CLAUDE.md §0-2).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query
from kayfabe.adapter.inbound.api.schemas.ai_lab_schema import (
    AgentActivitySchema,
    AgentAnalysisSchema,
    AgentReportSchema,
    AgentTotalsSchema,
    AiLabAgentsSchema,
    AiLabOverviewSchema,
    AiLabPredictionsSchema,
    IntegritySchema,
    PredictionEventSchema,
    PredictionItemSchema,
    PredictionTotalsSchema,
    RecentPredictionSchema,
    SystemComponentSchema,
)
from kayfabe.app.dtos.ai_lab_dto import (
    AiLabAgentsResponse,
    AiLabOverviewResponse,
    AiLabPredictionsResponse,
)
from kayfabe.app.ports.input.ai_lab_use_case import AiLabUseCase
from kayfabe.app.services.ai_lab_integrity import IntegrityFacts, PredictionTotals
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


@ai_lab_router.get(
    "/predictions",
    response_model=AiLabPredictionsSchema,
    response_model_by_alias=True,
)
async def list_ai_lab_predictions(
    agent: str | None = Query(default=None),
    use_case: AiLabUseCase = Depends(get_ai_lab),
):
    """저장된 예측 전체 + 에이전트 리포트 + 무결성 판정.

    **저장된 값만 읽는다** — LLM을 부르지도, 예측을 만들지도 않는다. 생성은 관리자
    전용 `POST /api/ple_events/{slug}/ai-predictions`와 배치 스크립트의 몫이다.

    리포트의 `sources`는 에이전트가 인용한 URL이지 **검색된 청크가 아니다.** 어떤
    청크가 어떤 유사도로 쓰였는지는 지금 구조가 기록하지 않는다.

    `agent`를 주면 그 에이전트가 리포트를 낸 예측만 남는다. 모르는 이름이면 빈
    목록이다 — 없음은 예외가 아니다.
    """
    logger.info("[AiLabRouter] list_ai_lab_predictions | agent=%s", agent or "-")
    return predictions_to_schema(await use_case.list_predictions(agent=agent))


@ai_lab_router.get(
    "/agents",
    response_model=AiLabAgentsSchema,
    response_model_by_alias=True,
)
async def get_ai_lab_agents(use_case: AiLabUseCase = Depends(get_ai_lab)):
    """에이전트별 응답률·의견률·정확도·가중치·자기 참조 출처 (Phase 3-3).

    **저장된 리포트만 읽는다** — LLM을 부르지 않는다. 정확도는 최종 예측이 아니라
    **그 에이전트의 의견**을 실제 승자와 대조한 값이다.
    """
    logger.info("[AiLabRouter] get_ai_lab_agents")
    return agents_to_schema(await use_case.get_agents())


def agents_to_schema(response: AiLabAgentsResponse) -> AiLabAgentsSchema:
    return AiLabAgentsSchema(
        totals=AgentTotalsSchema(
            agent_count=response.totals.agent_count,
            total_reports=response.totals.total_reports,
            opinionated=response.totals.opinionated,
            no_opinion=response.totals.no_opinion,
            overall_opinion_rate=response.totals.overall_opinion_rate,
            gradable_reports=response.totals.gradable_reports,
            total_predictions=response.totals.total_predictions,
        ),
        integrity=integrity_to_schema(response.integrity),
        agents=[
            AgentAnalysisSchema(
                agent=item.agent,
                reports=item.reports,
                with_pick=item.with_pick,
                no_opinion=item.no_opinion,
                response_rate=item.response_rate,
                opinion_rate=item.opinion_rate,
                gradable=item.gradable,
                correct=item.correct,
                incorrect=item.incorrect,
                accuracy=item.accuracy,
                accuracy_low=item.accuracy_low,
                accuracy_high=item.accuracy_high,
                avg_weight=item.avg_weight,
                avg_weight_opinionated=item.avg_weight_opinionated,
                matches_covered=item.matches_covered,
                events_covered=item.events_covered,
                self_referencing_reports=item.self_referencing_reports,
                uses_knowledge=item.uses_knowledge,
            )
            for item in response.agents
        ],
    )


def totals_to_schema(totals: PredictionTotals) -> PredictionTotalsSchema:
    return PredictionTotalsSchema(
        total=totals.total,
        graded=totals.graded,
        correct=totals.correct,
        incorrect=totals.incorrect,
        hit_rate=totals.hit_rate,
        hit_rate_low=totals.hit_rate_low,
        hit_rate_high=totals.hit_rate_high,
        avg_confidence=totals.avg_confidence,
        avg_win_probability=totals.avg_win_probability,
        bookmaker_fallback=totals.bookmaker_fallback,
    )


def integrity_to_schema(integrity: IntegrityFacts) -> IntegritySchema:
    return IntegritySchema(
        sample_size=integrity.sample_size,
        events_covered=integrity.events_covered,
        events_total=integrity.events_total,
        self_referencing_predictions=integrity.self_referencing_predictions,
        predictions_with_sources=integrity.predictions_with_sources,
        chunks_total=integrity.chunks_total,
        chunks_with_published_at=integrity.chunks_with_published_at,
        temporal_verifiable=integrity.temporal_verifiable,
        generalizable=integrity.generalizable,
        reasons=list(integrity.reasons),
    )


def predictions_to_schema(
    response: AiLabPredictionsResponse,
) -> AiLabPredictionsSchema:
    return AiLabPredictionsSchema(
        totals=totals_to_schema(response.totals),
        integrity=integrity_to_schema(response.integrity),
        events=[
            PredictionEventSchema(slug=e.slug, label=e.label, count=e.count)
            for e in response.events
        ],
        items=[
            PredictionItemSchema(
                event_slug=item.event_slug,
                event_label=item.event_label,
                match_key=item.match_key,
                match_title=item.match_title,
                pick=item.pick,
                pick_name=item.pick_name,
                win_probability=item.win_probability,
                confidence=item.confidence,
                rationale=item.rationale,
                source=item.source,
                generated_at=item.generated_at,
                winner_name=item.winner_name,
                correct=item.correct,
                reports=[
                    AgentReportSchema(
                        agent=report.agent,
                        pick=report.pick,
                        weight=report.weight,
                        summary=report.summary,
                        sources=list(report.sources),
                    )
                    for report in item.reports
                ],
            )
            for item in response.items
        ],
    )


def to_schema(response: AiLabOverviewResponse) -> AiLabOverviewSchema:
    return AiLabOverviewSchema(
        predictions=totals_to_schema(response.predictions),
        integrity=integrity_to_schema(response.integrity),
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
