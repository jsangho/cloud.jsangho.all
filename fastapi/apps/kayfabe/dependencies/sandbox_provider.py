"""장난감 시뮬레이터 배선.

**읽기 포트를 재사용한다.** `DataCenterRepository` 는 읽기 전용이라 이 유스케이스에
쓰기가 딸려 오지 않는다 — 새 포트를 낼 이유가 없다.
"""

from __future__ import annotations

from fastapi import Depends

from kayfabe.app.ports.input.sandbox_use_case import SandboxUseCase
from kayfabe.app.ports.output.data_center_repository import DataCenterRepository
from kayfabe.app.use_cases.sandbox_interactor import SandboxInteractor
from kayfabe.dependencies.data_center_provider import get_data_center_repository


def get_sandbox(
    repository: DataCenterRepository = Depends(get_data_center_repository),
) -> SandboxUseCase:
    return SandboxInteractor(data_center_repository=repository)
