from core.matrix.grid_oracle_database_manager import get_db
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import Depends
from kayfabe.adapter.outbound.pg.data_center_pg_repository import DataCenterPgRepository
from kayfabe.app.ports.input.data_center_use_case import DataCenterUseCase
from kayfabe.app.ports.output.data_center_repository import DataCenterRepository
from kayfabe.app.use_cases.data_center_interactor import DataCenterInteractor


def get_data_center_repository(
    db: AsyncSession = Depends(get_db),
) -> DataCenterRepository:
    return DataCenterPgRepository(db=db)


def get_data_center(
    repository: DataCenterRepository = Depends(get_data_center_repository),
) -> DataCenterUseCase:
    return DataCenterInteractor(data_center_repository=repository)
