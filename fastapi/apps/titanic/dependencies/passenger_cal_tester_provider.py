from core.matrix.grid_oracle_database_manager import get_db
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import Depends
from titanic.adapter.outbound.repositories.passenger_cal_tester_repository import (
    CalTesterRepository,
)
from titanic.app.ports.input.passenger_cal_tester_use_case import CalTesterUseCase
from titanic.app.ports.input.passenger_rose_model_use_case import RoseModelUseCase
from titanic.app.ports.output.passenger_cal_tester_port import CalTesterPort
from titanic.app.use_cases.passenger_cal_tester_interactor import CalTesterInteractor
from titanic.dependencies.passenger_rose_model_provider import get_rose_model


def get_cal_tester_repository(db: AsyncSession = Depends(get_db)) -> CalTesterPort:
    return CalTesterRepository(session=db)


def get_cal_tester(
    repository: CalTesterPort = Depends(get_cal_tester_repository),
    rose: RoseModelUseCase = Depends(get_rose_model),
) -> CalTesterUseCase:
    return CalTesterInteractor(repository=repository, rose=rose)
