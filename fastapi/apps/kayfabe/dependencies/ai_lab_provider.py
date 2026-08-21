from core.matrix.grid_oracle_database_manager import get_db
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import Depends
from kayfabe.adapter.outbound.pg.ai_lab_pg_repository import AiLabPgRepository
from kayfabe.app.ports.input.ai_lab_use_case import AiLabUseCase
from kayfabe.app.ports.output.ai_lab_repository import AiLabRepository
from kayfabe.app.use_cases.ai_lab_interactor import AiLabInteractor


def get_ai_lab_repository(db: AsyncSession = Depends(get_db)) -> AiLabRepository:
    return AiLabPgRepository(db=db)


def get_ai_lab(
    repository: AiLabRepository = Depends(get_ai_lab_repository),
) -> AiLabUseCase:
    return AiLabInteractor(repository=repository)
