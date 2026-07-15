from core.matrix.grid_oracle_database_manager import get_db
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import Depends
from titanic.adapter.outbound.repositories.crew_lowe_boat_repository import (
    LoweBoatRepository,
)
from titanic.app.ports.input.crew_lowe_boat_use_case import LoweBoatUseCase
from titanic.app.ports.output.crew_lowe_boat_port import LoweBoatPort
from titanic.app.use_cases.crew_lowe_boat_interactor import LoweBoatInteractor


def get_lowe_boat_repository(db: AsyncSession = Depends(get_db)) -> LoweBoatPort:
    return LoweBoatRepository(session=db)


def get_lowe_boat(
    repository: LoweBoatPort = Depends(get_lowe_boat_repository),
) -> LoweBoatUseCase:
    return LoweBoatInteractor(repository=repository)
