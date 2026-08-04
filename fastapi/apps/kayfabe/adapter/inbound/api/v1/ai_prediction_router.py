"""AI 멀티 에이전트 승부예측 엔드포인트.

**조회와 생성의 권한이 다르다.** 조회는 저장된 값을 읽기만 하므로 누구나 볼 수 있고,
생성은 LLM 비용이 드는 경로라 관리자만 부른다(하네스 §3-D1 · §7.2).
"""

from __future__ import annotations

from core.security.dependencies import RoleChecker
from core.security.role import UserRole
from core.security.token_verifier import TokenPayload

from fastapi import APIRouter, Depends, HTTPException
from kayfabe.adapter.inbound.api.schemas.ai_prediction_schema import (
    AgentPredictionListSchema,
    AgentPredictionSchema,
    AgentReportSchema,
    GeneratePredictionsRequest,
    GenerationSummarySchema,
)
from kayfabe.app.dtos.agent_prediction_dto import (
    AgentPredictionDto,
    GeneratePredictionCommand,
)
from kayfabe.app.ports.input.ai_prediction_use_case import AiPredictionUseCase
from kayfabe.app.ports.output.agent_prediction_repository import MatchNotFoundError
from kayfabe.dependencies.ai_prediction_provider import get_ai_prediction_use_case

ai_prediction_router = APIRouter(prefix="/ple_events", tags=["ple-ai-predictions"])

_admin_only = RoleChecker(UserRole.ADMIN)


@ai_prediction_router.get(
    "/{slug}/ai-predictions",
    response_model=AgentPredictionListSchema,
    response_model_by_alias=True,
)
async def list_ai_predictions(
    slug: str,
    use_case: AiPredictionUseCase = Depends(get_ai_prediction_use_case),
):
    """저장된 예측을 돌려준다. **LLM을 부르지 않는다** — 없으면 빈 목록이다."""
    items = await use_case.list_predictions(event_slug=slug)
    return AgentPredictionListSchema(items=[_to_schema(item) for item in items])


@ai_prediction_router.post(
    "/{slug}/ai-predictions",
    response_model=GenerationSummarySchema,
    response_model_by_alias=True,
)
async def generate_ai_predictions(
    slug: str,
    request: GeneratePredictionsRequest,
    _: TokenPayload = Depends(_admin_only),
    use_case: AiPredictionUseCase = Depends(get_ai_prediction_use_case),
):
    """에이전트를 돌려 예측을 만든다. 경기 하나가 실패해도 나머지는 계속 만든다."""
    try:
        summary = await use_case.generate(
            GeneratePredictionCommand(
                event_slug=slug,
                match_keys=tuple(request.match_keys),
                force=request.force,
            )
        )
    except MatchNotFoundError as exc:
        raise HTTPException(status_code=404, detail="경기를 찾을 수 없습니다.") from exc

    return GenerationSummarySchema(
        requested=summary.requested,
        generated=summary.generated,
        skipped=summary.skipped,
        failed=summary.failed,
    )


def _to_schema(dto: AgentPredictionDto) -> AgentPredictionSchema:
    return AgentPredictionSchema(
        match_key=dto.match_key,
        pick=dto.pick,
        pick_name=dto.pick_name,
        win_probability=dto.win_probability,
        confidence=dto.confidence,
        rationale=dto.rationale,
        source=dto.source,
        generated_at=dto.generated_at,
        reports=[
            AgentReportSchema(
                agent=report.agent,
                pick=report.pick,
                weight=report.weight,
                summary=report.summary,
                sources=list(report.sources),
            )
            for report in dto.reports
        ],
    )
