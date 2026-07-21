from __future__ import annotations

from ontology.app.dtos.image_classification_dto import ImageClassificationDto
from ontology.app.ports.input.image_classifier_use_case import ImageClassifierUseCase
from ontology.app.ports.output.image_label_classifier import ImageLabelClassifier


class ImageClassifierInteractor(ImageClassifierUseCase):
    def __init__(self, classifier: ImageLabelClassifier) -> None:
        self._classifier = classifier

    async def classify(self, image_bytes: bytes) -> ImageClassificationDto:
        return await self._classifier.classify(image_bytes)
