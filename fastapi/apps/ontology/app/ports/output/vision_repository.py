from __future__ import annotations

from abc import ABC, abstractmethod

from ontology.app.dtos.vision_dto import (
    VisionImageUploadResult,
    VisionQuery,
    VisionResponse,
)


class VisionRepository(ABC):
    @abstractmethod
    async def introduce_myself(self, query: VisionQuery) -> VisionResponse: ...

    @abstractmethod
    async def save_image(
        self, filename: str, content_type: str, content: bytes
    ) -> VisionImageUploadResult: ...
