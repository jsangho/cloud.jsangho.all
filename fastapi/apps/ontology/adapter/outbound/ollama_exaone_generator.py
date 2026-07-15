from __future__ import annotations

import json
import logging
import os
from collections.abc import AsyncIterator

import httpx

from ontology.app.dtos.exaone_generation_dto import ExaoneGenerationCommand
from ontology.app.ports.output.exaone_generation_port import ExaoneGenerationPort

logger = logging.getLogger("uvicorn.error")

_MODEL_ID = "exaone3.5:7.8b"


class OllamaExaoneGenerator(ExaoneGenerationPort):
    """Ollama 로컬 LLM(exaone3.5:7.8b)으로 텍스트를 스트리밍 생성하는 어댑터."""

    def __init__(self, host: str | None = None) -> None:
        self._host = host or os.environ.get("OLLAMA_HOST", "http://localhost:11434")

    async def stream_generate(
        self, command: ExaoneGenerationCommand
    ) -> AsyncIterator[str]:
        logger.info(
            "[ontology.ollama_exaone_generator] Ollama 호출 시작 | model=%s | host=%s",
            _MODEL_ID,
            self._host,
        )
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST",
                f"{self._host}/api/generate",
                json={"model": _MODEL_ID, "prompt": command.prompt, "stream": True},
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    data = json.loads(line)
                    text = data.get("response", "")
                    if text:
                        yield text
                    if data.get("done"):
                        break
        logger.info(
            "[ontology.ollama_exaone_generator] Ollama 호출 종료 | model=%s", _MODEL_ID
        )
