from admin.adapter.outbound.repositories.piper_dunn_coo_repository import (
    DunnCooRepository,
)
from admin.app.ports.input.piper_dunn_coo_use_case import DunnCooUseCase
from admin.app.ports.output.piper_dunn_coo_port import DunnCooPort
from admin.app.use_cases.piper_dunn_coo_interactor import DunnCooInteractor
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.matrix.grid_oracle_database_manager import get_db


def get_dunn_coo_repository(
    db: AsyncSession = Depends(get_db),
) -> DunnCooPort:
    return DunnCooRepository(session=db)


def get_dunn_coo(
    repository: DunnCooPort = Depends(get_dunn_coo_repository),
) -> DunnCooUseCase:
    return DunnCooInteractor(repository=repository)
