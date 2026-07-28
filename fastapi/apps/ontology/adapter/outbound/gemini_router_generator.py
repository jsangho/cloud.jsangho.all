from __future__ import annotations

import logging

from core.matrix.vault_keymaker_secret_manager import get_keymaker
from google import genai
from google.genai import types

from ontology.app.dtos.semantic_routing_dto import (
    ROUTING_SYSTEM_PROMPT,
    SemanticRoutingCommand,
)
from ontology.app.ports.output.semantic_routing_port import SemanticRoutingPort

logger = logging.getLogger("uvicorn.error")

_MODEL_ID = "gemini-3.5-flash"

_ROUTING_RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "destination": {
            "type": "STRING",
            "enum": ["crud", "exaone_rag", "gemini"],
        },
        "entities": {"type": "ARRAY", "items": {"type": "STRING"}},
    },
    "required": ["destination", "entities"],
}


class GeminiRouterGenerator(SemanticRoutingPort):
    """Ollama가 없는 환경(운영 서버 등)을 위한 Gemini 기반 의도 분류 어댑터.

    프롬프트·출력 스키마는 `OllamaQwenRouterGenerator`와 동일하게 맞춰
    인터랙터의 파싱·가드레일 로직을 그대로 재사용한다.
    """

    def __init__(self) -> None:
        self._client = genai.Client(api_key=get_keymaker().get_gemini_api_key())

    async def classify(self, command: SemanticRoutingCommand) -> str:
        logger.info(
            "[ontology.gemini_router_generator] Gemini 라우팅 호출 시작 | model=%s",
            _MODEL_ID,
        )
        response = await self._client.aio.models.generate_content(
            model=_MODEL_ID,
            contents=command.question,
            config=types.GenerateContentConfig(
                system_instruction=ROUTING_SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_schema=_ROUTING_RESPONSE_SCHEMA,
            ),
        )
        logger.info(
            "[ontology.gemini_router_generator] Gemini 라우팅 호출 종료 | model=%s",
            _MODEL_ID,
        )
        return response.text or ""
