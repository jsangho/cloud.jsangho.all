from admin.adapter.outbound.repositories.piper_gilfoyle_sys_repository import (
    GilfoyleSysRepository,
)
from admin.app.ports.input.piper_gilfoyle_sys_use_case import (
    GilfoyleSysUseCase,
)
from admin.app.ports.output.piper_gilfoyle_sys_port import GilfoyleSysPort
from admin.app.use_cases.piper_gilfoyle_sys_interactor import (
    GilfoyleSysInteractor,
)
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.matrix.grid_oracle_database_manager import get_db


def get_gilfoyle_sys_repository(
    db: AsyncSession = Depends(get_db),
) -> GilfoyleSysPort:
    return GilfoyleSysRepository(session=db)


def get_gilfoyle_sys(
    repository: GilfoyleSysPort = Depends(get_gilfoyle_sys_repository),
) -> GilfoyleSysUseCase:
    return GilfoyleSysInteractor(repository=repository)
