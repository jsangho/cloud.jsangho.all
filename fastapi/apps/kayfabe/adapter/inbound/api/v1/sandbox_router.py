"""장난감 시뮬레이터 라우터.

**`/sandbox` 로 격리한 것은 결정이다.** `/ple-matches` 나 `/ai-lab` 아래 두면
장난감 확률이 실제 예측과 같은 자리에서 나오고, 응답만 떼어 보면 구별할 수 없다.
경로 이름이 그 구별의 절반이고 나머지 절반은 화면 문구다.

**쓰기 엔드포인트가 없다.** `GET` 하나뿐이고 DB에 아무것도 남기지 않는다 —
그 제약이 이전 커리어 시뮬레이터가 38,326줄로 불어난 길을 막는다
(`domain/services/match_sim` 독스트링의 "안 만드는 것" 참조).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from kayfabe.adapter.inbound.api.schemas.sandbox_schema import (
    SimContenderSchema,
    SimResultSchema,
)
from kayfabe.app.dtos.sandbox_dto import SimContenderResponse, SimResultResponse
from kayfabe.app.ports.input.sandbox_use_case import SandboxUseCase
from kayfabe.dependencies.sandbox_provider import get_sandbox

logger = logging.getLogger("uvicorn.error")

sandbox_router = APIRouter(prefix="/sandbox", tags=["sandbox"])


@sandbox_router.get("/simulate", response_model=SimResultSchema)
async def simulate_match(
    a: str = Query(min_length=1, description="선수 A"),
    b: str = Query(min_length=1, description="선수 B"),
    use_case: SandboxUseCase = Depends(get_sandbox),
):
    """두 선수를 붙여 승자를 뽑는다. **장난감이다 — 예측이 아니다.**"""
    logger.info("[SandboxRouter] simulate a=%s b=%s", a, b)
    result = await use_case.simulate(a=a, b=b)
    if result is None:
        raise HTTPException(status_code=404, detail="로스터에 없는 선수입니다")
    return _to_schema(result)


def _contender_to_schema(dto: SimContenderResponse) -> SimContenderSchema:
    return SimContenderSchema(
        name=dto.name, titles=dto.titles, age=dto.age, score=dto.score
    )


def _to_schema(dto: SimResultResponse) -> SimResultSchema:
    return SimResultSchema(
        a=_contender_to_schema(dto.a),
        b=_contender_to_schema(dto.b),
        winner=dto.winner,
        probability_a=dto.probability_a,
        roll=dto.roll,
    )
