from core.matrix.grid_oracle_database_manager import get_db
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import Depends
from titanic.adapter.outbound.repositories.crew_andrews_architect_repository import (
    AndrewsArchitectRepository,
)
from titanic.app.ports.input.crew_andrews_architect_use_case import (
    AndrewsArchitectUseCase,
)
from titanic.app.ports.output.crew_andrews_architect_port import AndrewsArchitectPort
from titanic.app.use_cases.crew_andrews_architect_interactor import (
    AndrewsArchitectInteractor,
)


def get_andrews_architect_repository(
    db: AsyncSession = Depends(get_db),
) -> AndrewsArchitectPort:
    return AndrewsArchitectRepository(session=db)


def get_andrews_architect(
    repository: AndrewsArchitectPort = Depends(get_andrews_architect_repository),
) -> AndrewsArchitectUseCase:
    return AndrewsArchitectInteractor(repository=repository)
