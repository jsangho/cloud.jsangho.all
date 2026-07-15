from core.matrix.grid_oracle_database_manager import get_db
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import Depends
from kayfabe.adapter.outbound.pg.ple_events_pg_repository import PleEventsPgRepository
from kayfabe.app.ports.input.ple_events_use_case import PleEventsUseCase
from kayfabe.app.ports.output.ple_events_repository import PleEventsRepository
from kayfabe.app.use_cases.ple_events_interactor import PleEventsInteractor


def get_ple_events_repository(
    db: AsyncSession = Depends(get_db),
) -> PleEventsRepository:
    return PleEventsPgRepository(db=db)


def get_ple_events(
    repository: PleEventsRepository = Depends(get_ple_events_repository),
) -> PleEventsUseCase:
    return PleEventsInteractor(repository=repository)
