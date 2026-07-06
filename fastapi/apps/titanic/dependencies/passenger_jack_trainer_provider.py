from core.matrix.grid_oracle_database_manager import get_db
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import Depends
from titanic.adapter.outbound.repositories.passenger_jack_trainer_repository import (
    JackTrainerRepository,
)
from titanic.app.ports.input.passenger_jack_trainer_use_case import JackTrainerUseCase
from titanic.app.ports.output.passenger_jack_trainer_port import JackTrainerPort
from titanic.app.use_cases.passenger_jack_trainer_interactor import (
    JackTrainerInteractor,
)


def get_jack_trainer_repository(db: AsyncSession = Depends(get_db)) -> JackTrainerPort:
    return JackTrainerRepository(session=db)


def get_jack_trainer(
    repository: JackTrainerPort = Depends(get_jack_trainer_repository),
) -> JackTrainerUseCase:
    return JackTrainerInteractor(repository=repository)
