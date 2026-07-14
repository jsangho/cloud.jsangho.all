from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from ontology.app.dtos.exaone_generation_dto import ExaoneGenerationCommand


class ExaoneGenerationPort(ABC):
    @abstractmethod
    def stream_generate(
        self, command: ExaoneGenerationCommand
    ) -> AsyncIterator[str]: ...
