from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from ontology.app.dtos.gemini_generation_dto import GeminiGenerationCommand


class GeminiGenerationPort(ABC):
    @abstractmethod
    def stream_generate(
        self, command: GeminiGenerationCommand
    ) -> AsyncIterator[str]: ...
