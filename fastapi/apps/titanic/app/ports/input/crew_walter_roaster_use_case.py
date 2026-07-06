from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import pandas as pd

from titanic.app.dtos.crew_walter_roaster_dto import (
    WalterRoasterQuery,
    WalterRoasterResponse,
)


class WalterRoasterUseCase(ABC):
    @abstractmethod
    async def get_train_set(self) -> pd.DataFrame:
        """월터가 DB에서 train_set을 가져오는 메소드"""
        ...

    @abstractmethod
    async def get_test_set(self) -> pd.DataFrame:
        """월터가 DB에서 test_set을 가져오는 메소드"""
        ...

    @abstractmethod
    async def introduce_myself(
        self, query: WalterRoasterQuery
    ) -> WalterRoasterResponse:
        """윌터 자기소개 메소드 (`GET /myself`)."""
        ...

    @abstractmethod
    async def list_openfile_page(self, *, page: int, page_size: int) -> dict[str, Any]:
        """승객 명단 페이지 조회 (`GET /openfile`)."""
        ...
