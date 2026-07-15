from __future__ import annotations

from ontology.adapter.outbound.ollama_exaone_generator import OllamaExaoneGenerator
from ontology.app.ports.input.exaone_generation_use_case import (
    ExaoneGenerationUseCase,
)
from ontology.app.use_cases.exaone_generation_interactor import (
    ExaoneGenerationInteractor,
)


def get_exaone_generation_use_case() -> ExaoneGenerationUseCase:
    return ExaoneGenerationInteractor(generator=OllamaExaoneGenerator())
