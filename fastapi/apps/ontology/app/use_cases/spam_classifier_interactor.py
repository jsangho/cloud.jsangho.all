from __future__ import annotations

from ontology.app.dtos.spam_classification_dto import SpamClassificationDto
from ontology.app.ports.input.spam_classifier_use_case import SpamClassifierUseCase
from ontology.app.ports.output.spam_label_classifier import SpamLabelClassifier


class SpamClassifierInteractor(SpamClassifierUseCase):
    def __init__(self, classifier: SpamLabelClassifier) -> None:
        self._classifier = classifier

    async def classify(self, subject: str, body: str) -> SpamClassificationDto:
        return await self._classifier.classify(subject, body)

    async def initialize(self) -> None:
        """LLM 기반 분류기는 별도 시드 작업이 필요 없다."""
