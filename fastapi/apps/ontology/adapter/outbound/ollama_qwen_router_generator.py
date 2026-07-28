from __future__ import annotations

import logging
import os

import httpx

from ontology.app.dtos.semantic_routing_dto import (
    ROUTING_SYSTEM_PROMPT,
    SemanticRoutingCommand,
)
from ontology.app.ports.output.semantic_routing_port import SemanticRoutingPort

logger = logging.getLogger("uvicorn.error")

_MODEL_ID = "qwen2.5:1.5b"


class OllamaQwenRouterGenerator(SemanticRoutingPort):
    """Ollama 로컬 LLM(qwen2.5:1.5b)으로 질문 의도를 분류하는 어댑터."""

    def __init__(self, host: str | None = None) -> None:
        self._host = host or os.environ.get("OLLAMA_HOST", "http://localhost:11434")

    async def classify(self, command: SemanticRoutingCommand) -> str:
        logger.info(
            "[ontology.ollama_qwen_router_generator] Ollama 호출 시작 | model=%s | host=%s",
            _MODEL_ID,
            self._host,
        )
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self._host}/api/generate",
                json={
                    "model": _MODEL_ID,
                    "system": ROUTING_SYSTEM_PROMPT,
                    "prompt": command.question,
                    "format": "json",
                    "stream": False,
                },
            )
            response.raise_for_status()
            raw = response.json().get("response", "")
        logger.info(
            "[ontology.ollama_qwen_router_generator] Ollama 호출 종료 | model=%s",
            _MODEL_ID,
        )
        return raw
