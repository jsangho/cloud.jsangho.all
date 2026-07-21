from __future__ import annotations

from ontology.app.dtos.video_classification_dto import VideoClassificationDto
from ontology.app.ports.input.video_classifier_use_case import VideoClassifierUseCase
from ontology.app.ports.output.video_label_classifier import VideoLabelClassifier


class VideoClassifierInteractor(VideoClassifierUseCase):
    def __init__(self, classifier: VideoLabelClassifier) -> None:
        self._classifier = classifier

    async def classify(self, video_bytes: bytes) -> VideoClassificationDto:
        return await self._classifier.classify(video_bytes)
