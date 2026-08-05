from core.matrix.grid_oracle_database_manager import get_db
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import Depends
from kayfabe.adapter.outbound.agents.odds_scout_agent import BookmakerOddsScout
from kayfabe.adapter.outbound.agents.pending_agents import (
    PendingRumorScout,
    PendingStorylineAnalyst,
)
from kayfabe.adapter.outbound.pg.agent_prediction_pg_repository import (
    AgentPredictionPgRepository,
)
from kayfabe.adapter.outbound.repositories.prediction_knowledge_repository import (
    PredictionKnowledgeRepository,
)
from kayfabe.app.ports.input.ai_prediction_use_case import AiPredictionUseCase
from kayfabe.app.ports.output.agent_prediction_repository import (
    AgentPredictionRepository,
)
from kayfabe.app.ports.output.prediction_knowledge_port import PredictionKnowledgePort
from kayfabe.app.use_cases.ai_prediction_interactor import AiPredictionInteractor


def get_agent_prediction_repository(
    db: AsyncSession = Depends(get_db),
) -> AgentPredictionRepository:
    return AgentPredictionPgRepository(db=db)


def get_prediction_knowledge(
    db: AsyncSession = Depends(get_db),
) -> PredictionKnowledgePort:
    return PredictionKnowledgeRepository(db)


def get_ai_prediction_use_case(
    repository: AgentPredictionRepository = Depends(get_agent_prediction_repository),
    knowledge: PredictionKnowledgePort = Depends(get_prediction_knowledge),
) -> AiPredictionUseCase:
    """오즈와 지식 검색은 실제 구현이고 서사·루머는 아직 임시 어댑터다.

    T3(수집)가 오기 전까지 `ple_knowledge_chunks`는 비어 있어 검색 결과가 0건이다 —
    **실패가 아니라 아직 아는 게 없는 상태다.** T5가 오면 이 함수의 인자만 바뀐다.
    """
    return AiPredictionInteractor(
        repository,
        knowledge,
        PendingStorylineAnalyst(),
        BookmakerOddsScout(),
        PendingRumorScout(),
    )
