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
    CareerStateSchema,
    CareerStepRequest,
    CareerStepSchema,
    SimContenderSchema,
    SimResultSchema,
)
from kayfabe.app.dtos.sandbox_dto import (
    CareerStepResponse,
    SimContenderResponse,
    SimResultResponse,
)
from kayfabe.app.ports.input.sandbox_use_case import SandboxUseCase
from kayfabe.dependencies.sandbox_provider import get_sandbox
from kayfabe.domain.services.career_run import CHOICES, CareerState

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


@sandbox_router.post("/career/step", response_model=CareerStepSchema)
async def career_step(
    body: CareerStepRequest,
    use_case: SandboxUseCase = Depends(get_sandbox),
):
    """커리어 한 주를 넘긴다. **저장하지 않는다.**

    `POST` 인 것은 본문으로 상태를 받기 때문이고 **쓰기 때문이 아니다.** 서버는
    상태를 모른다 — 런을 들고 다니는 쪽은 브라우저다. 그래서 세이브·불러오기·
    버전 호환이 생기지 않는다(이전 커리어 시뮬이 38,326줄로 불어난 사슬의 시작이
    `career_runs` 테이블이었다).
    """
    if body.choice not in CHOICES:
        raise HTTPException(status_code=422, detail=f"choice 는 {CHOICES} 중 하나")
    logger.info(
        "[SandboxRouter] career_step name=%s week=%d choice=%s",
        body.state.name,
        body.state.week,
        body.choice,
    )
    result = await use_case.career_step(state=_to_state(body.state), choice=body.choice)
    return _career_to_schema(result)


def _to_state(schema: CareerStateSchema) -> CareerState:
    return CareerState(
        name=schema.name,
        style=schema.style,
        week=schema.week,
        brand=schema.brand,
        popularity=schema.popularity,
        wins=schema.wins,
        losses=schema.losses,
        reigns=tuple(schema.reigns),
        held=schema.held,
        out_weeks=schema.out_weeks,
        outcome=schema.outcome,
    )


def _career_to_schema(dto: CareerStepResponse) -> CareerStepSchema:
    return CareerStepSchema(
        state=CareerStateSchema(
            name=dto.state.name,
            style=dto.state.style,
            week=dto.state.week,
            brand=dto.state.brand,
            popularity=dto.state.popularity,
            wins=dto.state.wins,
            losses=dto.state.losses,
            reigns=dto.state.reigns,
            held=dto.state.held,
            out_weeks=dto.state.out_weeks,
            outcome=dto.state.outcome,
        ),
        week=dto.week,
        kind=dto.kind,
        won=dto.won,
        opponent=dto.opponent,
        belt=dto.belt,
        max_weeks=dto.max_weeks,
        promoted_to=dto.promoted_to,
        injured_weeks=dto.injured_weeks,
        popularity_delta=dto.popularity_delta,
        next_belt=dto.next_belt,
        defending=dto.defending,
    )
