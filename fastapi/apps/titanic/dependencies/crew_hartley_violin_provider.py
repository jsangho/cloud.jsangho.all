from core.matrix.grid_oracle_database_manager import get_db
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import Depends
from titanic.adapter.outbound.repositories.crew_hartley_violin_repository import (
    HartleyViolinRepository,
)
from titanic.app.ports.input.crew_hartley_violin_use_case import HartleyViolinUseCase
from titanic.app.ports.output.crew_hartley_violin_port import HartleyViolinPort
from titanic.app.use_cases.crew_hartley_violin_interactor import HartleyViolinInteractor


def get_hartley_violin_repository(
    db: AsyncSession = Depends(get_db),
) -> HartleyViolinPort:
    return HartleyViolinRepository(session=db)


def get_hartley_violin(
    repository: HartleyViolinPort = Depends(get_hartley_violin_repository),
) -> HartleyViolinUseCase:
    return HartleyViolinInteractor(repository=repository)
