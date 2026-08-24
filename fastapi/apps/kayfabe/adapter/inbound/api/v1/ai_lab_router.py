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
    AgentContributionSchema,
    AgentReportSchema,
    AgentTotalsSchema,
    AiLabAgentsSchema,
    AiLabEvaluationSchema,
    AiLabKnowledgeSchema,
    AiLabOverviewSchema,
    AiLabPerformanceSchema,
    AiLabPredictionsSchema,
    ConsensusLevelSchema,
    EligiblePerformanceSchema,
    EvaluationItemSchema,
    EvaluationRuleSchema,
    EvaluationTotalsSchema,
    InferentialSchema,
    IntegritySchema,
    KnowledgeDocumentSchema,
    KnowledgeDomainSchema,
    KnowledgeTotalsSchema,
    PerformanceItemSchema,
    PerformanceTotalsSchema,
    PredictionEventSchema,
    PredictionItemSchema,
    PredictionTotalsSchema,
    RecentPredictionSchema,
    ReportContributionSchema,
    RuleVerdictSchema,
    SystemComponentSchema,
)
from kayfabe.app.dtos.ai_lab_dto import (
    AiLabAgentsResponse,
    AiLabEvaluationResponse,
    AiLabKnowledgeResponse,
    AiLabOverviewResponse,
    AiLabPerformanceResponse,
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


@ai_lab_router.get(
    "/evaluation",
    response_model=AiLabEvaluationSchema,
    response_model_by_alias=True,
)
async def get_ai_lab_evaluation(use_case: AiLabUseCase = Depends(get_ai_lab)):
    """어떤 예측이 채점 대상이 될 **자격**이 있는가 (Phase 3-6).

    **성능을 재는 응답이 아니다.** 3-0이 표본 수준에서 "이 적중률을 믿어도 되는가"를
    물었다면, 여기서는 예측 하나하나가 애초에 분모에 들어갈 자격이 있는지를 판정한다.

    `performance`는 **자격 있는 표본이 있을 때만** 만들어진다. 0건이면 `null`이다 —
    0%도 빈 객체도 아니다.

    `severity`가 실격(`disqualify`)과 보류(`hold`)를 가른다. 보류는 누수를 증명도
    반증도 못 한 상태이고, 통과가 아니다.

    **추정하지 않는다.** `ple_prediction_retrievals`가 없으므로 어떤 청크가 실제로
    검색됐는지는 판정에 쓰지 않는다. 저장된 출처 URL까지가 확인 가능한 전부다.
    """
    logger.info("[AiLabRouter] get_ai_lab_evaluation")
    return evaluation_to_schema(await use_case.get_evaluation())


def evaluation_to_schema(response: AiLabEvaluationResponse) -> AiLabEvaluationSchema:
    return AiLabEvaluationSchema(
        totals=EvaluationTotalsSchema(
            predictions=response.totals.predictions,
            fallback=response.totals.fallback,
            pending=response.totals.pending,
            disqualified=response.totals.disqualified,
            held=response.totals.held,
            eligible=response.totals.eligible,
        ),
        integrity=integrity_to_schema(response.integrity),
        rules=[
            EvaluationRuleSchema(
                code=rule.code,
                label=rule.label,
                severity=rule.severity,
                description=rule.description,
                blocked=rule.blocked,
            )
            for rule in response.rules
        ],
        items=[
            EvaluationItemSchema(
                event_slug=item.event_slug,
                event_label=item.event_label,
                match_key=item.match_key,
                match_title=item.match_title,
                generated_at=item.generated_at,
                result_recorded_at=item.result_recorded_at,
                status=item.status,
                eligible=item.eligible,
                verdicts=[
                    RuleVerdictSchema(
                        code=verdict.code,
                        failed=verdict.failed,
                        applicable=verdict.applicable,
                        detail=verdict.detail,
                    )
                    for verdict in item.verdicts
                ],
            )
            for item in response.items
        ],
        # 자격이 0건이면 `None`을 그대로 내보낸다 — 여기서 0%를 만들지 않는다.
        performance=(
            None
            if response.performance is None
            else EligiblePerformanceSchema(
                sample=response.performance.sample,
                correct=response.performance.correct,
                incorrect=response.performance.incorrect,
                accuracy=response.performance.accuracy,
                accuracy_low=response.performance.accuracy_low,
                accuracy_high=response.performance.accuracy_high,
                events_covered=response.performance.events_covered,
            )
        ),
    )


@ai_lab_router.get(
    "/performance",
    response_model=AiLabPerformanceSchema,
    response_model_by_alias=True,
)
async def get_ai_lab_performance(use_case: AiLabUseCase = Depends(get_ai_lab)):
    """최종 승률이 세 의견에서 **어떻게 접혔는지** (Phase 3-5).

    **정확도를 재는 응답이 아니다.** 전체 적중률은 `/overview`가, 에이전트별
    정확도는 `/agents`가 이미 낸다. 여기 실린 `correct`·`graded`는 그 숫자를 다시
    세우기 위한 것이 아니라 각 합의 층의 **분모를 밝히기 위한** 것이다.

    `consensus`는 `confidence` 값이 아니라 `(answered, agreed)` 짝으로 묶인다 —
    곱이 같으면 서로 다른 상황이 한 줄로 접히기 때문이다.

    저장된 값만 읽는다. LLM도 임베딩도 부르지 않는다.
    """
    logger.info("[AiLabRouter] get_ai_lab_performance")
    return performance_to_schema(await use_case.get_performance())


def performance_to_schema(
    response: AiLabPerformanceResponse,
) -> AiLabPerformanceSchema:
    return AiLabPerformanceSchema(
        totals=PerformanceTotalsSchema(
            predictions=response.totals.predictions,
            graded=response.totals.graded,
            correct=response.totals.correct,
            incorrect=response.totals.incorrect,
            bookmaker_fallback=response.totals.bookmaker_fallback,
            singles=response.totals.singles,
            multi=response.totals.multi,
        ),
        integrity=integrity_to_schema(response.integrity),
        inferential=InferentialSchema(
            available=response.inferential.available,
            reasons=list(response.inferential.reasons),
        ),
        consensus=[
            ConsensusLevelSchema(
                confidence=level.confidence,
                answered=level.answered,
                agreed=level.agreed,
                predictions=level.predictions,
                graded=level.graded,
                correct=level.correct,
            )
            for level in response.consensus
        ],
        contributions=[
            AgentContributionSchema(
                agent=item.agent,
                reports=item.reports,
                opinions=item.opinions,
                distinct_weights=item.distinct_weights,
                min_weight=item.min_weight,
                max_weight=item.max_weight,
                constant=item.constant,
            )
            for item in response.contributions
        ],
        items=[
            PerformanceItemSchema(
                event_slug=item.event_slug,
                event_label=item.event_label,
                match_key=item.match_key,
                match_title=item.match_title,
                win_probability=item.win_probability,
                confidence=item.confidence,
                agreement=item.agreement,
                coverage=item.coverage,
                correct=item.correct,
                reports=[
                    ReportContributionSchema(
                        agent=report.agent,
                        weight=report.weight,
                        opinionated=report.opinionated,
                    )
                    for report in item.reports
                ],
            )
            for item in response.items
        ],
    )


@ai_lab_router.get(
    "/knowledge",
    response_model=AiLabKnowledgeSchema,
    response_model_by_alias=True,
)
async def get_ai_lab_knowledge(use_case: AiLabUseCase = Depends(get_ai_lab)):
    """RAG 코퍼스 문서 목록 + **그중 실제로 프롬프트에 들어간 문서** (Phase 3-4).

    **검색을 돌리지 않는다.** 저장된 리포트의 출처 URL과 문서 목록을 맞춰 볼 뿐이라
    임베딩도 LLM도 부르지 않는다.

    `usedByReports`가 셀 수 있는 값인 이유는 저장된 출처가 LLM이 쓴 문장이 아니라
    **실제로 프롬프트에 넣은 청크의 URL**이기 때문이다. 다만 리포트당 상위 5청크·최대
    5출처만 남으므로 이 수치는 **하한**이다.
    """
    logger.info("[AiLabRouter] get_ai_lab_knowledge")
    return knowledge_to_schema(await use_case.get_knowledge())


def knowledge_to_schema(response: AiLabKnowledgeResponse) -> AiLabKnowledgeSchema:
    return AiLabKnowledgeSchema(
        totals=KnowledgeTotalsSchema(
            documents=response.totals.documents,
            chunks=response.totals.chunks,
            chunks_embedded=response.totals.chunks_embedded,
            chunks_with_published_at=response.totals.chunks_with_published_at,
            domains=response.totals.domains,
            last_collected_at=response.totals.last_collected_at,
            used_documents=response.totals.used_documents,
            used_document_rate=response.totals.used_document_rate,
            reports_total=response.totals.reports_total,
            reports_with_sources=response.totals.reports_with_sources,
            sources_outside_corpus=response.totals.sources_outside_corpus,
        ),
        integrity=integrity_to_schema(response.integrity),
        documents=[
            KnowledgeDocumentSchema(
                source_url=item.source_url,
                source_domain=item.source_domain,
                title=item.title,
                chunks=item.chunks,
                chunks_embedded=item.chunks_embedded,
                chunks_with_published_at=item.chunks_with_published_at,
                first_published_at=item.first_published_at,
                last_collected_at=item.last_collected_at,
                used_by_reports=item.used_by_reports,
                used_by_agents=list(item.used_by_agents),
            )
            for item in response.documents
        ],
        domains=[
            KnowledgeDomainSchema(
                domain=item.domain,
                documents=item.documents,
                chunks=item.chunks,
                used_documents=item.used_documents,
            )
            for item in response.domains
        ],
    )


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
