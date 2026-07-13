from admin.adapter.outbound.repositories.piper_bighetti_hr_repository import (
    BighettiHrRepository,
)
from admin.app.ports.input.piper_bighetti_hr_use_case import BighettiHrUseCase
from admin.app.ports.output.piper_bighetti_hr_port import BighettiHrPort
from admin.app.use_cases.piper_bighetti_hr_interactor import (
    BighettiHrInteractor,
)
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.matrix.grid_oracle_database_manager import get_db


def get_bighetti_hr_repository(
    db: AsyncSession = Depends(get_db),
) -> BighettiHrPort:
    return BighettiHrRepository(session=db)


def get_bighetti_hr(
    repository: BighettiHrPort = Depends(get_bighetti_hr_repository),
) -> BighettiHrUseCase:
    return BighettiHrInteractor(repository=repository)
