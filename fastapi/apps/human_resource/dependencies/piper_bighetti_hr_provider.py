from core.matrix.grid_oracle_database_manager import get_db
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import Depends
from human_resource.adapter.outbound.repositories.piper_bighetti_hr_repository import (
    BighettiHrRepository,
)
from human_resource.app.ports.input.piper_bighetti_hr_use_case import BighettiHrUseCase
from human_resource.app.ports.output.piper_bighetti_hr_port import BighettiHrPort
from human_resource.app.use_cases.piper_bighetti_hr_interactor import (
    BighettiHrInteractor,
)


def get_bighetti_hr_repository(
    db: AsyncSession = Depends(get_db),
) -> BighettiHrPort:
    return BighettiHrRepository(session=db)


def get_bighetti_hr(
    repository: BighettiHrPort = Depends(get_bighetti_hr_repository),
) -> BighettiHrUseCase:
    return BighettiHrInteractor(repository=repository)
