from core.matrix.grid_oracle_database_manager import get_db
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import Depends
from human_resource.adapter.outbound.repositories.piper_hendricks_ceo_repository import (
    HendricksCeoRepository,
)
from human_resource.app.ports.input.piper_hendricks_ceo_use_case import (
    HendricksCeoUseCase,
)
from human_resource.app.ports.output.piper_hendricks_ceo_port import HendricksCeoPort
from human_resource.app.use_cases.piper_hendricks_ceo_interactor import (
    HendricksCeoInteractor,
)


def get_hendricks_ceo_repository(
    db: AsyncSession = Depends(get_db),
) -> HendricksCeoPort:
    return HendricksCeoRepository(session=db)


def get_hendricks_ceo(
    repository: HendricksCeoPort = Depends(get_hendricks_ceo_repository),
) -> HendricksCeoUseCase:
    return HendricksCeoInteractor(repository=repository)
