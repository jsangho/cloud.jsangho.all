from core.matrix.grid_oracle_database_manager import get_db
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import Depends
from kayfabe.adapter.outbound.pg.ple_match_pick_pg_repository import (
    PleMatchPickPgRepository,
)
from kayfabe.app.ports.input.ple_match_pick_use_case import PleMatchPickUseCase
from kayfabe.app.ports.output.ple_match_pick_repository import PleMatchPickRepository
from kayfabe.app.use_cases.ple_match_pick_interactor import PleMatchPickInteractor


def get_ple_match_pick_repository(
    db: AsyncSession = Depends(get_db),
) -> PleMatchPickRepository:
    return PleMatchPickPgRepository(db=db)


def get_ple_match_pick(
    repository: PleMatchPickRepository = Depends(get_ple_match_pick_repository),
) -> PleMatchPickUseCase:
    return PleMatchPickInteractor(repository=repository)
