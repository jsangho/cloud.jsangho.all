from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.matrix.grid_oracle_database_manager import get_db
from kayfabe.adapter.outbound.pg.ple_events_pg_repository import PleEventsPgRepository
from kayfabe.app.ports.input.event_status_use_case import EventStatusUseCase
from kayfabe.app.ports.output.event_status_repository import EventStatusRepository
from kayfabe.app.use_cases.event_status_interactor import EventStatusInteractor


def get_event_status_repository(
    db: AsyncSession = Depends(get_db),
) -> EventStatusRepository:
    return PleEventsPgRepository(db=db)


def get_event_status_use_case(
    repository: EventStatusRepository = Depends(get_event_status_repository),
) -> EventStatusUseCase:
    return EventStatusInteractor(repository=repository)
