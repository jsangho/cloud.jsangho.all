from __future__ import annotations

import os

from ontology.adapter.outbound.gemini_router_generator import GeminiRouterGenerator
from ontology.adapter.outbound.ollama_qwen_router_generator import (
    OllamaQwenRouterGenerator,
)
from ontology.app.ports.input.semantic_routing_use_case import SemanticRoutingUseCase
from ontology.app.ports.output.semantic_routing_port import SemanticRoutingPort
from ontology.app.use_cases.semantic_routing_interactor import (
    SemanticRoutingInteractor,
)

_PROVIDER_ENV = "SEMANTIC_ROUTING_PROVIDER"


def _build_classifier() -> SemanticRoutingPort:
    """Ollama가 없는 환경(운영 서버 등)에서는 `SEMANTIC_ROUTING_PROVIDER=gemini`로
    전환한다. 기본값은 기존 로컬 개발 동작(Ollama)을 그대로 유지한다."""
    if os.environ.get(_PROVIDER_ENV, "ollama").strip().lower() == "gemini":
        return GeminiRouterGenerator()
    return OllamaQwenRouterGenerator()


def get_semantic_routing_use_case() -> SemanticRoutingUseCase:
    return SemanticRoutingInteractor(classifier=_build_classifier())
