from __future__ import annotations

from abc import ABC, abstractmethod

from human_resource.app.dtos.piper_gilfoyle_sys_dto import (
    GilfoyleSysQuery,
    GilfoyleSysResponse,
)


class GilfoyleSysUseCase(ABC):
    """`/human_resource/gilfoyle/*` inbound(gilfoyle_sys_router) 입력 포트."""

    @abstractmethod
    async def introduce_myself(self, query: GilfoyleSysQuery) -> GilfoyleSysResponse:
        """버트램 길포일의 자기소개 메소드 (`GET /myself`)."""
        ...
