from __future__ import annotations

from abc import ABC, abstractmethod

from ontology.app.dtos.spam_classification_dto import SpamClassificationDto


class SpamClassifierUseCase(ABC):
    @abstractmethod
    async def classify(self, subject: str, body: str) -> SpamClassificationDto: ...

    @abstractmethod
    async def initialize(self) -> None: ...
