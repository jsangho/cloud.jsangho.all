from core.matrix.grid_oracle_database_manager import get_db
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import Depends
from kayfabe.adapter.outbound.agents.pending_agents import (
    EmptyPredictionKnowledge,
    PendingOddsScout,
    PendingRumorScout,
    PendingStorylineAnalyst,
)
from kayfabe.adapter.outbound.pg.agent_prediction_pg_repository import (
    AgentPredictionPgRepository,
)
from kayfabe.app.ports.input.ai_prediction_use_case import AiPredictionUseCase
from kayfabe.app.ports.output.agent_prediction_repository import (
    AgentPredictionRepository,
)
from kayfabe.app.use_cases.ai_prediction_interactor import AiPredictionInteractor


def get_agent_prediction_repository(
    db: AsyncSession = Depends(get_db),
) -> AgentPredictionRepository:
    return AgentPredictionPgRepository(db=db)


def get_ai_prediction_use_case(
    repository: AgentPredictionRepository = Depends(get_agent_prediction_repository),
) -> AiPredictionUseCase:
    """지금은 분석기 자리에 임시 어댑터가 들어간다.

    T4(검색)·T5(에이전트)가 오면 이 함수의 인자만 바뀐다 — 유스케이스와 라우터는
    그대로다. 그것이 포트를 먼저 정의한 이유다.
    """
    return AiPredictionInteractor(
        repository,
        EmptyPredictionKnowledge(),
        PendingStorylineAnalyst(),
        PendingOddsScout(),
        PendingRumorScout(),
    )
