from __future__ import annotations

import os

from core.matrix.vault_keymaker_secret_manager import get_keymaker
from ontology.adapter.outbound.groq_generator import GroqGenerator
from ontology.app.ports.input.gemini_generation_use_case import (
    GeminiGenerationUseCase,
)
from ontology.app.use_cases.gemini_interactor import GeminiInteractor


def get_groq_generation_use_case() -> GeminiGenerationUseCase | None:
    """`GROQ_API_KEY` 가 없으면 `None` — 예비가 없을 뿐 기동은 막지 않는다.

    포트 이름이 `Gemini…` 인 것은 역사적 이유다. 계약(프롬프트 → 텍스트 조각)은
    벤더와 무관해서 그대로 꽂힌다.
    """
    get_keymaker().load_env()
    key = (os.getenv("GROQ_API_KEY") or "").strip()
    if not key:
        return None
    return GeminiInteractor(generator=GroqGenerator(api_key=key))
