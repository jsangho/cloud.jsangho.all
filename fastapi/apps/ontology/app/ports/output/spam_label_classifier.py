from __future__ import annotations

from abc import ABC, abstractmethod

from ontology.app.dtos.spam_classification_dto import SpamClassificationDto


class SpamLabelClassifier(ABC):
    @abstractmethod
    async def classify(self, subject: str, body: str) -> SpamClassificationDto: ...
