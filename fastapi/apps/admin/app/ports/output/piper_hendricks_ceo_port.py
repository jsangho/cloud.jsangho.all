from __future__ import annotations

from abc import ABC, abstractmethod

from admin.app.dtos.piper_hendricks_ceo_dto import (
    HendricksCeoQuery,
    HendricksCeoResponse,
)


class HendricksCeoPort(ABC):
    @abstractmethod
    async def introduce_myself(self, query: HendricksCeoQuery) -> HendricksCeoResponse:
        pass
