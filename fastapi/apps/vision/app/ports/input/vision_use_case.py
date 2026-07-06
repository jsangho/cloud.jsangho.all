from __future__ import annotations

from abc import ABC, abstractmethod

from vision.app.dtos.vision_dto import (
    VisionImageUploadResult,
    VisionQuery,
    VisionResponse,
)


class VisionUseCase(ABC):
    """`/vision/*` inbound 입력 포트."""

    @abstractmethod
    async def introduce_myself(self, query: VisionQuery) -> VisionResponse:
        """Vision 서비스 자기소개."""
        ...

    @abstractmethod
    async def upload_image(
        self, filename: str, content_type: str, content: bytes
    ) -> VisionImageUploadResult:
        """업로드된 이미지를 저장한다."""
        ...
