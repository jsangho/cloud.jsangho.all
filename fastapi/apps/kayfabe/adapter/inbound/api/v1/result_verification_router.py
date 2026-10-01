"""결과 확정 에이전트 엔드포인트 — **관리자 전용**.

이 에이전트는 끝난 대회의 결과 미기록 경기를 위키에서 찾아 `winner_pick`을 채운다.
그 값은 채점·적중률·포인트 집계의 입력이라(`point_aggregation`), 한 번 잘못 쓰면
사용자 점수가 조용히 틀어진다. 그래서 문을 셋으로 나눠 뒀다.

1. `GET .../pending` — **모델을 부르지 않는다.** 무엇을 볼지만 보여준다.
2. `POST .../run` (기본 `apply=false`) — 돌려 보고 쓰지 않는다.
3. `POST .../run` + `apply=true` — 쓴다. **토큰의 `sub`를 로그에 남긴다.**

프로바이더 독스트링에 적혀 있던 "라우터에 열지 않는다"는 이전 결정을 뒤집은 것이며,
그 이유와 대체 장치는 그쪽 독스트링에 적어 두었다.

**경기 하나에 모델을 여러 번 부르고 호출 간격을 벌린다**(무료 등급 분당 5회). 그래서
화면은 경기를 한 건씩 보내고, 이쪽은 `matchKeys`로 그것을 받는다 — 대회 전체를 한
요청에 묶으면 중간 프록시가 먼저 끊는다.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from core.security.dependencies import RoleChecker
from core.security.role import UserRole
from core.security.token_verifier import TokenPayload
from kayfabe.adapter.inbound.api.schemas.result_verification_schema import (
    MatchVerificationSchema,
    PendingMatchListSchema,
    PendingMatchSchema,
    VerificationRunSchema,
    VerifyResultsRequest,
)
from kayfabe.app.dtos.result_verification_dto import (
    VerificationRun,
    VerifyResultsCommand,
)
from kayfabe.app.ports.input.result_verification_use_case import (
    ResultVerificationUseCase,
)
from kayfabe.dependencies.result_verification_provider import get_result_verification

logger = logging.getLogger("uvicorn.error")

result_verification_router = APIRouter(
    prefix="/ple_events", tags=["ple-result-verification"]
)

_admin_only = RoleChecker(UserRole.ADMIN)

# 경로가 `/maintenance/...` 아래인 것은 `GET /ple_events/{slug}`가 한 칸짜리 경로를
# slug로 먹기 때문이다 (`event_status_router`와 같은 이유).


@result_verification_router.get(
    "/maintenance/result-verification/pending",
    response_model=PendingMatchListSchema,
    response_model_by_alias=True,
)
async def list_pending_results(
    event_slug: str | None = None,
    _: TokenPayload = Depends(_admin_only),
    use_case: ResultVerificationUseCase = Depends(get_result_verification),
):
    """결과가 없는 경기 목록. **모델을 부르지 않으므로 비용이 없다.**"""
    matches = await use_case.list_pending(event_slug=event_slug)
    return PendingMatchListSchema(
        items=[
            PendingMatchSchema(
                eventSlug=match.event_slug,
                eventLabel=match.event_label,
                matchKey=match.match_key,
                title=match.title,
                options=[option.name for option in match.options],
            )
            for match in matches
        ]
    )


@result_verification_router.post(
    "/maintenance/result-verification/run",
    response_model=VerificationRunSchema,
    response_model_by_alias=True,
)
async def run_result_verification(
    request: VerifyResultsRequest,
    claims: TokenPayload = Depends(_admin_only),
    use_case: ResultVerificationUseCase = Depends(get_result_verification),
):
    """에이전트를 돌린다. `apply`가 참일 때만 쓴다.

    보류는 실패가 아니다 — 승자를 못 찾은 것은 정상 종료이고, 틀린 승자를 쓰는 것만
    사고다. 한 경기의 장애도 보류로 끝나고 나머지는 계속 간다.
    """
    if request.apply:
        # **쓰기는 누가 했는지 남긴다.** 스크립트 경로에는 이 기록이 없었다.
        logger.info(
            "[kayfabe.result_agent] 쓰기 요청 | actor=%s event=%s matches=%s",
            claims.sub,
            request.event_slug or "-",
            list(request.match_keys) or "-",
        )

    run = await use_case.verify(
        VerifyResultsCommand(
            event_slug=request.event_slug,
            match_keys=tuple(request.match_keys),
            limit=request.limit,
            apply=request.apply,
        )
    )
    return _to_schema(run)


def _to_schema(run: VerificationRun) -> VerificationRunSchema:
    return VerificationRunSchema(
        matches=[
            MatchVerificationSchema(
                eventSlug=match.event_slug,
                matchKey=match.match_key,
                title=match.title,
                pick=match.pick,
                winnerName=match.winner_name,
                hold=str(match.hold) if match.hold is not None else None,
                written=match.written,
                quote=match.quote,
                sourceTitle=match.source_title,
                sourceRevisionId=match.source_revision_id,
                toolCalls=match.tool_calls,
            )
            for match in run.matches
        ],
        applied=run.applied,
        found=run.found,
        written=run.written,
        writable=run.writable,
        held=run.held,
        toolCalls=run.tool_calls,
    )
