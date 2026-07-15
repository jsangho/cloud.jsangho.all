from admin.adapter.outbound.repositories.piper_dinesh_dash_repository import (
    DineshDashRepository,
)
from admin.app.ports.input.piper_dinesh_dash_use_case import DineshDashUseCase
from admin.app.ports.output.piper_dinesh_dash_port import DineshDashPort
from admin.app.use_cases.piper_dinesh_dash_interactor import (
    DineshDashInteractor,
)
from core.matrix.grid_oracle_database_manager import get_db
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import Depends


def get_dinesh_dash_repository(
    db: AsyncSession = Depends(get_db),
) -> DineshDashPort:
    return DineshDashRepository(session=db)


def get_dinesh_dash(
    repository: DineshDashPort = Depends(get_dinesh_dash_repository),
) -> DineshDashUseCase:
    return DineshDashInteractor(repository=repository)
