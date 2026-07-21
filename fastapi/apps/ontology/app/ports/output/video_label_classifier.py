from __future__ import annotations

from abc import ABC, abstractmethod

from ontology.app.dtos.video_classification_dto import VideoClassificationDto


class VideoLabelClassifier(ABC):
    @abstractmethod
    async def classify(self, video_bytes: bytes) -> VideoClassificationDto: ...
