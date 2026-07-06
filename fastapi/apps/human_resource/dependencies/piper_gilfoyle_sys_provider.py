from core.matrix.grid_oracle_database_manager import get_db
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import Depends
from human_resource.adapter.outbound.repositories.piper_gilfoyle_sys_repository import (
    GilfoyleSysRepository,
)
from human_resource.app.ports.input.piper_gilfoyle_sys_use_case import (
    GilfoyleSysUseCase,
)
from human_resource.app.ports.output.piper_gilfoyle_sys_port import GilfoyleSysPort
from human_resource.app.use_cases.piper_gilfoyle_sys_interactor import (
    GilfoyleSysInteractor,
)


def get_gilfoyle_sys_repository(
    db: AsyncSession = Depends(get_db),
) -> GilfoyleSysPort:
    return GilfoyleSysRepository(session=db)


def get_gilfoyle_sys(
    repository: GilfoyleSysPort = Depends(get_gilfoyle_sys_repository),
) -> GilfoyleSysUseCase:
    return GilfoyleSysInteractor(repository=repository)
