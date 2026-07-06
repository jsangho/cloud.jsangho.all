from __future__ import annotations

from vision.app.dtos.vision_dto import (
    VisionImageUploadResult,
    VisionQuery,
    VisionResponse,
)
from vision.app.ports.input.vision_use_case import VisionUseCase
from vision.app.ports.output.vision_repository import VisionRepository


class VisionInteractor(VisionUseCase):
    def __init__(self, repository: VisionRepository) -> None:
        self._repository = repository

    async def introduce_myself(self, query: VisionQuery) -> VisionResponse:
        return await self._repository.introduce_myself(query)

    async def upload_image(
        self, filename: str, content_type: str, content: bytes
    ) -> VisionImageUploadResult:
        return await self._repository.save_image(filename, content_type, content)
