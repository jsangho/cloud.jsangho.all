from core.matrix.grid_oracle_database_manager import get_db
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import Depends
from kayfabe.adapter.outbound.pg.ple_matches_pg_repository import PleMatchesPgRepository
from kayfabe.app.ports.input.ple_matches_use_case import PleMatchesUseCase
from kayfabe.app.ports.output.ple_matches_repository import PleMatchesRepository
from kayfabe.app.use_cases.ple_matches_interactor import PleMatchesInteractor


def get_ple_matches_repository(
    db: AsyncSession = Depends(get_db),
) -> PleMatchesRepository:
    return PleMatchesPgRepository(db=db)


def get_ple_matches(
    repository: PleMatchesRepository = Depends(get_ple_matches_repository),
) -> PleMatchesUseCase:
    return PleMatchesInteractor(records_repository=repository)
