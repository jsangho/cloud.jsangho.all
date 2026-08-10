"""커리어 시뮬레이터의 Depends 팩토리 (하네스 §6).

**서술 어댑터는 상태가 없어 하나를 돌려 쓴다** — `RuleNarrator`는 시드 고정 순수 함수의
얇은 껍데기라 요청마다 새로 만들 이유가 없다(§3-D9). 리포지토리만 세션에 묶인다.
"""

from __future__ import annotations

from core.matrix.grid_oracle_database_manager import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from wwe_game.adapter.outbound.narration.rule_narrator import RuleNarrator
from wwe_game.adapter.outbound.pg.career_pg_repository import CareerPgRepository
from wwe_game.app.ports.input.career_use_case import CareerUseCase
from wwe_game.app.ports.output.career_repository import CareerRepository
from wwe_game.app.ports.output.narration_port import NarrationPort
from wwe_game.app.use_cases.career_interactor import CareerInteractor

from fastapi import Depends

_NARRATOR: NarrationPort = RuleNarrator()


def get_career_repository(db: AsyncSession = Depends(get_db)) -> CareerRepository:
    return CareerPgRepository(db)


def get_career_use_case(
    repository: CareerRepository = Depends(get_career_repository),
) -> CareerUseCase:
    return CareerInteractor(repository=repository, narrator=_NARRATOR)
