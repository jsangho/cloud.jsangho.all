"""커리어 샌드박스 배선.

**무상태 장난감(`sandbox_provider`)과 별개다.** 그쪽은 읽기 전용 포트를 재사용하고
이쪽은 쓰기가 있는 세이브 저장소를 쓴다.

## `CAREER_V3_WRITES_ENABLED`

서버 환경변수에서만 읽는다 — 요청에서 이 값을 받는 경로가 없다. **정확히 `true` 만
연다.** 미설정·빈 문자열·오타·`1`·`TRUE` 는 전부 닫힘이다: 값을 잘못 적었을 때 쓰기가
막히는 쪽은 503 으로 드러나 고치면 되지만, 열리는 쪽은 세이브가 v3 로 바뀌어 되돌리는
데 복구 절차가 든다. `.env` 를 고친 뒤에는 재기동해야 프로세스가 새 값을 본다.
"""

from __future__ import annotations

import os

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.matrix.grid_oracle_database_manager import get_db
from kayfabe.adapter.outbound.pg.sandbox_career_pg_repository import (
    SandboxCareerPgRepository,
)
from kayfabe.app.ports.input.career_sandbox_use_case import CareerSandboxUseCase
from kayfabe.app.ports.output.data_center_repository import DataCenterRepository
from kayfabe.app.ports.output.sandbox_career_repository import SandboxCareerRepository
from kayfabe.app.use_cases.career_sandbox_interactor import CareerSandboxInteractor
from kayfabe.dependencies.data_center_provider import get_data_center_repository

CAREER_V3_WRITES_ENV = "CAREER_V3_WRITES_ENABLED"


def career_v3_writes_enabled() -> bool:
    return os.getenv(CAREER_V3_WRITES_ENV) == "true"


def get_career_repository(
    db: AsyncSession = Depends(get_db),
) -> SandboxCareerRepository:
    return SandboxCareerPgRepository(
        db=db, v3_writes_enabled=career_v3_writes_enabled()
    )


def get_career_use_case(
    repository: SandboxCareerRepository = Depends(get_career_repository),
    data_center: DataCenterRepository = Depends(get_data_center_repository),
) -> CareerSandboxUseCase:
    # 실제 현역 명부는 읽기 전용 포트를 재사용한다(`sandbox_provider` 와 같은 길).
    return CareerSandboxInteractor(repository=repository, data_center=data_center)
