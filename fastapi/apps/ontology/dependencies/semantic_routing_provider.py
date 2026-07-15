from __future__ import annotations

from ontology.adapter.outbound.ollama_qwen_router_generator import (
    OllamaQwenRouterGenerator,
)
from ontology.app.ports.input.semantic_routing_use_case import SemanticRoutingUseCase
from ontology.app.use_cases.semantic_routing_interactor import (
    SemanticRoutingInteractor,
)


def get_semantic_routing_use_case() -> SemanticRoutingUseCase:
    return SemanticRoutingInteractor(classifier=OllamaQwenRouterGenerator())
