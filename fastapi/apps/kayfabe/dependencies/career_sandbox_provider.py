"""커리어 샌드박스 배선.

**무상태 장난감(`sandbox_provider`)과 별개다.** 그쪽은 읽기 전용 포트를 재사용하고
이쪽은 쓰기가 있는 세이브 저장소를 쓴다.
"""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.matrix.grid_oracle_database_manager import get_db
from kayfabe.adapter.outbound.pg.sandbox_career_pg_repository import (
    SandboxCareerPgRepository,
)
from kayfabe.app.ports.input.career_sandbox_use_case import CareerSandboxUseCase
from kayfabe.app.ports.output.sandbox_career_repository import SandboxCareerRepository
from kayfabe.app.use_cases.career_sandbox_interactor import CareerSandboxInteractor


def get_career_repository(
    db: AsyncSession = Depends(get_db),
) -> SandboxCareerRepository:
    return SandboxCareerPgRepository(db=db)


def get_career_use_case(
    repository: SandboxCareerRepository = Depends(get_career_repository),
) -> CareerSandboxUseCase:
    return CareerSandboxInteractor(repository=repository)
