from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.matrix.grid_oracle_database_manager import get_db
from kayfabe.adapter.outbound.repositories.wrestler_chat_repository import (
    WrestlerChatRepository,
)
from kayfabe.app.ports.input.wrestler_chat_use_case import WrestlerChatUseCase
from kayfabe.app.ports.output.wrestler_chat_port import WrestlerChatPort
from kayfabe.app.use_cases.wrestler_chat_interactor import WrestlerChatInteractor


def get_wrestler_chat_repository(
    db: AsyncSession = Depends(get_db),
) -> WrestlerChatPort:
    return WrestlerChatRepository(session=db)


def get_wrestler_chat_use_case(
    repository: WrestlerChatPort = Depends(get_wrestler_chat_repository),
) -> WrestlerChatUseCase:
    return WrestlerChatInteractor(repository=repository)
