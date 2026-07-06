from __future__ import annotations

from abc import ABC, abstractmethod

from human_resource.app.dtos.piper_dunn_coo_dto import DunnCooQuery, DunnCooResponse


class DunnCooUseCase(ABC):
    """`/human_resource/dunn/*` inbound(dunn_coo_router) 입력 포트."""

    @abstractmethod
    async def introduce_myself(self, query: DunnCooQuery) -> DunnCooResponse:
        """재러드 던의 자기소개 메소드 (`GET /myself`)."""
        ...
