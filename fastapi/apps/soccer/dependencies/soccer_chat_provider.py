from core.matrix.grid_oracle_database_manager import get_db
from soccer.adapter.outbound.repositories.soccer_chat_repository import (
    SoccerChatRepository,
)
from soccer.app.ports.input.soccer_chat_use_case import SoccerChatUseCase
from soccer.app.ports.output.soccer_chat_port import SoccerChatPort
from soccer.app.use_cases.soccer_chat_interactor import SoccerChatInteractor
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import Depends
from ontology.app.ports.input.gemini_generation_use_case import (
    GeminiGenerationUseCase,
)
from ontology.dependencies.gemini_generation_provider import (
    get_gemini_generation_use_case,
)


def get_soccer_chat_repository(
    db: AsyncSession = Depends(get_db),
    generation_use_case: GeminiGenerationUseCase = Depends(
        get_gemini_generation_use_case
    ),
) -> SoccerChatPort:
    return SoccerChatRepository(session=db, generation_use_case=generation_use_case)


def get_soccer_chat_use_case(
    repository: SoccerChatPort = Depends(get_soccer_chat_repository),
) -> SoccerChatUseCase:
    return SoccerChatInteractor(repository=repository)
