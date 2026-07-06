from core.matrix.grid_oracle_database_manager import get_db
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import Depends
from titanic.adapter.outbound.repositories.passenger_isidor_couple_repository import (
    IsidorCoupleRepository,
)
from titanic.app.ports.input.passenger_isidor_couple_use_case import IsidorCoupleUseCase
from titanic.app.ports.output.passenger_isidor_couple_port import IsidorCouplePort
from titanic.app.use_cases.passenger_isidor_couple_interactor import (
    IsidorCoupleInteractor,
)


def get_isidor_couple_repository(
    db: AsyncSession = Depends(get_db),
) -> IsidorCouplePort:
    return IsidorCoupleRepository(session=db)


def get_isidor_couple(
    repository: IsidorCouplePort = Depends(get_isidor_couple_repository),
) -> IsidorCoupleUseCase:
    return IsidorCoupleInteractor(repository=repository)
