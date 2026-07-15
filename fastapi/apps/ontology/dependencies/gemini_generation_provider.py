from __future__ import annotations

from ontology.adapter.outbound.gemini_generator import GeminiGenerator
from ontology.app.ports.input.gemini_generation_use_case import (
    GeminiGenerationUseCase,
)
from ontology.app.use_cases.gemini_interactor import GeminiInteractor


def get_gemini_generation_use_case() -> GeminiGenerationUseCase:
    return GeminiInteractor(generator=GeminiGenerator())
