from core.matrix.grid_oracle_database_manager import get_db
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import Depends
from kayfabe.adapter.outbound.agents.odds_scout_agent import BookmakerOddsScout
from kayfabe.adapter.outbound.agents.rumor_scout_agent import GeminiRumorScout
from kayfabe.adapter.outbound.agents.storyline_gemini_agent import (
    GeminiStorylineAnalyst,
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
from ontology.app.ports.input.gemini_generation_use_case import GeminiGenerationUseCase
from ontology.dependencies.gemini_generation_provider import (
    get_gemini_generation_use_case,
)


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
    generation: GeminiGenerationUseCase = Depends(get_gemini_generation_use_case),
) -> AiPredictionUseCase:
    """세 에이전트가 모두 실물이다.

    **지식이 비어 있는 동안은 LLM 호출이 0회다** — 서사·루머 에이전트가 출처 있는
    자료를 못 받으면 모델을 부르지 않고 의견 없음을 낸다. 그래서 적재 전에는 오즈
    한 표로만 예측이 만들어지고, 비용도 들지 않는다.
    """
    return AiPredictionInteractor(
        repository,
        knowledge,
        GeminiStorylineAnalyst(generation),
        BookmakerOddsScout(),
        GeminiRumorScout(generation),
    )
