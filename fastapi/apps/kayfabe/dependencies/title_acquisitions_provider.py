from core.matrix.grid_oracle_database_manager import get_db
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import Depends
from kayfabe.adapter.outbound.pg.title_acquisitions_pg_repository import (
    TitleAcquisitionsPgRepository,
)
from kayfabe.app.ports.input.title_acquisitions_use_case import TitleAcquisitionsUseCase
from kayfabe.app.ports.output.title_acquisitions_repository import (
    TitleAcquisitionsRepository,
)
from kayfabe.app.use_cases.title_acquisitions_interactor import (
    TitleAcquisitionsInteractor,
)


def get_title_acquisitions_repository(
    db: AsyncSession = Depends(get_db),
) -> TitleAcquisitionsRepository:
    return TitleAcquisitionsPgRepository(db=db)


def get_title_acquisitions(
    repository: TitleAcquisitionsRepository = Depends(
        get_title_acquisitions_repository
    ),
) -> TitleAcquisitionsUseCase:
    return TitleAcquisitionsInteractor(title_Acquisitions_repository=repository)
