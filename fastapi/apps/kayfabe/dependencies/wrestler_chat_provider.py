from core.matrix.grid_oracle_database_manager import get_db
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import Depends
from kayfabe.adapter.outbound.repositories.wrestler_chat_repository import (
    WrestlerChatRepository,
)
from kayfabe.app.ports.input.wrestler_chat_use_case import WrestlerChatUseCase
from kayfabe.app.ports.output.wrestler_chat_port import WrestlerChatPort
from kayfabe.app.use_cases.wrestler_chat_interactor import WrestlerChatInteractor
from ontology.app.ports.input.exaone_generation_use_case import (
    ExaoneGenerationUseCase,
)
from ontology.dependencies.exaone_generation_provider import (
    get_exaone_generation_use_case,
)


def get_wrestler_chat_repository(
    db: AsyncSession = Depends(get_db),
    generation_use_case: ExaoneGenerationUseCase = Depends(
        get_exaone_generation_use_case
    ),
) -> WrestlerChatPort:
    return WrestlerChatRepository(session=db, generation_use_case=generation_use_case)


def get_wrestler_chat_use_case(
    repository: WrestlerChatPort = Depends(get_wrestler_chat_repository),
) -> WrestlerChatUseCase:
    return WrestlerChatInteractor(repository=repository)
