"""AI 승부예측 조립.

**에이전트마다 다른 Gemini 모델을 쓴다.** 무료 등급의 호출 한도가 모델 단위라,
같은 모델을 공유하면 서사가 쓴 만큼 루머가 못 쓴다. 모델 ID는 환경변수로 두어
모델이 은퇴하거나 더 나은 것이 나왔을 때 `.env` 한 줄로 바꾼다.
"""

from __future__ import annotations

import os

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

#: 서사 추론은 판단이 어렵다 — 좋은 모델을 준다.
DEFAULT_STORYLINE_MODEL = "gemini-3.6-flash"

#: 루머는 "자료에 부상·복귀 사실이 있나, 없으면 null"이라 가벼운 모델로 충분하다.
DEFAULT_RUMOR_MODEL = "gemini-3.5-flash-lite"


def _model(env_key: str, default: str) -> str:
    return (os.getenv(env_key) or "").strip() or default


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
    """세 에이전트가 모두 실물이고, LLM 둘은 서로 다른 모델을 쓴다.

    **지식이 비어 있는 동안은 LLM 호출이 0회다** — 서사·루머 에이전트가 출처 있는
    자료를 못 받으면 모델을 부르지 않고 의견 없음을 낸다. 그래서 적재 전에는 오즈
    한 표로만 예측이 만들어지고, 비용도 들지 않는다.
    """
    return AiPredictionInteractor(
        repository,
        knowledge,
        GeminiStorylineAnalyst(
            generation, model=_model("GEMINI_MODEL_STORYLINE", DEFAULT_STORYLINE_MODEL)
        ),
        BookmakerOddsScout(),
        GeminiRumorScout(
            generation, model=_model("GEMINI_MODEL_RUMOR", DEFAULT_RUMOR_MODEL)
        ),
    )
