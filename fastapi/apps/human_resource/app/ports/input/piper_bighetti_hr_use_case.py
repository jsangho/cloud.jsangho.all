from __future__ import annotations

from abc import ABC, abstractmethod

from human_resource.app.dtos.piper_bighetti_hr_dto import (
    BighettiHrQuery,
    BighettiHrResponse,
)


class BighettiHrUseCase(ABC):
    """`/human_resource/bighetti/*` inbound(bighetti_hr_router) 입력 포트."""

    @abstractmethod
    async def introduce_myself(self, query: BighettiHrQuery) -> BighettiHrResponse:
        """넬슨 빅헤드 비게티의 자기소개 메소드 (`GET /myself`)."""
        ...
