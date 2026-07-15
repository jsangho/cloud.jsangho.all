from core.matrix.grid_oracle_database_manager import get_db
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import Depends
from titanic.adapter.outbound.repositories.passenger_molly_scaler_repository import (
    MollyScalerRepository,
)
from titanic.app.ports.input.passenger_molly_scaler_use_case import MollyScalerUseCase
from titanic.app.ports.output.passenger_molly_scaler_port import MollyScalerPort
from titanic.app.use_cases.passenger_molly_scaler_interactor import (
    MollyScalerInteractor,
)


def get_molly_scaler_repository(db: AsyncSession = Depends(get_db)) -> MollyScalerPort:
    return MollyScalerRepository(session=db)


def get_molly_scaler(
    repository: MollyScalerPort = Depends(get_molly_scaler_repository),
) -> MollyScalerUseCase:
    return MollyScalerInteractor(repository=repository)
