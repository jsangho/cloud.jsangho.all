from __future__ import annotations

from abc import ABC, abstractmethod

from ontology.app.dtos.image_classification_dto import ImageClassificationDto


class ImageClassifierUseCase(ABC):
    @abstractmethod
    async def classify(self, image_bytes: bytes) -> ImageClassificationDto: ...
