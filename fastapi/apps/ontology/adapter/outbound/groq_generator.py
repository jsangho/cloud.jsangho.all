from __future__ import annotations

import logging
from collections.abc import AsyncIterator

import httpx

from ontology.app.dtos.gemini_generation_dto import GeminiGenerationCommand
from ontology.app.ports.output.gemini_generation_port import GeminiGenerationPort

logger = logging.getLogger("uvicorn.error")

GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"

#: 2026-11-12 실측(끝난 9경기)에서 판단 방향이 Gemini와 3/3 일치한 모델.
DEFAULT_GROQ_MODEL = "openai/gpt-oss-120b"

_TIMEOUT_SECONDS = 60.0


class GroqGenerator(GeminiGenerationPort):
    """Groq(OpenAI 호환 API)로 텍스트를 생성하는 어댑터.

    Gemini 무료 등급(모델당 하루 20회)이 바닥났을 때의 **다른 회사 예비**다.
    한도가 회사 단위로 갈리므로 Gemini가 막힌 날에도 이쪽은 살아 있다.

    스트리밍하지 않고 한 번에 받아 한 조각으로 흘려보낸다 — 응답이 짧고(JSON 한 개),
    부르는 쪽은 어차피 이어 붙인다.
    """

    def __init__(self, api_key: str, *, default_model: str = DEFAULT_GROQ_MODEL):
        self._api_key = api_key
        self._default_model = default_model

    async def stream_generate(
        self, command: GeminiGenerationCommand
    ) -> AsyncIterator[str]:
        model = command.model or self._default_model
        logger.info("[ontology.groq_generator] Groq 호출 시작 | model=%s", model)
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            response = await client.post(
                GROQ_CHAT_URL,
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": command.prompt}],
                    "temperature": 0.3,
                },
            )
            response.raise_for_status()
            body = response.json()
        text = body["choices"][0]["message"].get("content") or ""
        # 추론 모델이 생각을 본문에 섞어 보내는 경우가 있다 — 답만 남긴다.
        if "</think>" in text:
            text = text.split("</think>", 1)[1]
        logger.info("[ontology.groq_generator] Groq 호출 종료 | model=%s", model)
        yield text
