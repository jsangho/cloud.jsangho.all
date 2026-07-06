from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from titanic.app.dtos.crew_walter_roaster_dto import (
    WalterRoasterQuery,
    WalterRoasterResponse,
)


class WalterRoasterPort(ABC):
    @abstractmethod
    async def get_train_set(self):
        """Survived 컬럼이 있는 데이터 전체를 데이터프레임으로 반환하는 메소드"""
        pass

    @abstractmethod
    async def get_test_set(self):
        """Survived 컬럼이 없는 데이터 전체를 데이터프레임으로 반환하는 메소드"""
        pass

    @abstractmethod
    async def introduce_myself(
        self, query: WalterRoasterQuery
    ) -> WalterRoasterResponse:
        pass

    @abstractmethod
    async def list_openfile_page(
        self, *, page: int, page_size: int
    ) -> dict[str, Any]: ...
