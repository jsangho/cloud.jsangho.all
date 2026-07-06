from __future__ import annotations

from abc import ABC, abstractmethod

from human_resource.app.dtos.piper_dinesh_dash_dto import (
    DineshDashQuery,
    DineshDashResponse,
)


class DineshDashUseCase(ABC):
    """`/human_resource/dinesh/*` inbound(dinesh_dash_router) 입력 포트."""

    @abstractmethod
    async def introduce_myself(self, query: DineshDashQuery) -> DineshDashResponse:
        """디네시 추타이의 자기소개 메소드 (`GET /myself`)."""
        ...
