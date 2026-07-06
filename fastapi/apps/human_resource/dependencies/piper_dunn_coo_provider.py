from core.matrix.grid_oracle_database_manager import get_db
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import Depends
from human_resource.adapter.outbound.repositories.piper_dunn_coo_repository import (
    DunnCooRepository,
)
from human_resource.app.ports.input.piper_dunn_coo_use_case import DunnCooUseCase
from human_resource.app.ports.output.piper_dunn_coo_port import DunnCooPort
from human_resource.app.use_cases.piper_dunn_coo_interactor import DunnCooInteractor


def get_dunn_coo_repository(
    db: AsyncSession = Depends(get_db),
) -> DunnCooPort:
    return DunnCooRepository(session=db)


def get_dunn_coo(
    repository: DunnCooPort = Depends(get_dunn_coo_repository),
) -> DunnCooUseCase:
    return DunnCooInteractor(repository=repository)
