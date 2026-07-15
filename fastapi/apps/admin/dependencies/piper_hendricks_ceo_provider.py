from admin.adapter.outbound.repositories.piper_hendricks_ceo_repository import (
    HendricksCeoRepository,
)
from admin.app.ports.input.piper_hendricks_ceo_use_case import (
    HendricksCeoUseCase,
)
from admin.app.ports.output.piper_hendricks_ceo_port import HendricksCeoPort
from admin.app.use_cases.piper_hendricks_ceo_interactor import (
    HendricksCeoInteractor,
)
from core.matrix.grid_oracle_database_manager import get_db
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import Depends


def get_hendricks_ceo_repository(
    db: AsyncSession = Depends(get_db),
) -> HendricksCeoPort:
    return HendricksCeoRepository(session=db)


def get_hendricks_ceo(
    repository: HendricksCeoPort = Depends(get_hendricks_ceo_repository),
) -> HendricksCeoUseCase:
    return HendricksCeoInteractor(repository=repository)
