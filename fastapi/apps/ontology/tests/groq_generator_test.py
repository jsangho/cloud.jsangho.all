"""Groq 어댑터 — 네트워크 없이 요청 모양과 응답 판독만 본다."""

import sys
from pathlib import Path

import httpx
import pytest

_APPS_DIR = str(Path(__file__).resolve().parents[2])
if _APPS_DIR not in sys.path:
    sys.path.insert(0, _APPS_DIR)

from ontology.adapter.outbound import groq_generator  # noqa: E402
from ontology.adapter.outbound.groq_generator import (  # noqa: E402
    DEFAULT_GROQ_MODEL,
    GroqGenerator,
)
from ontology.app.dtos.gemini_generation_dto import (  # noqa: E402
    GeminiGenerationCommand,
)


def _patch_transport(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    real = httpx.AsyncClient

    def fake_client(*args, **kwargs):
        return real(*args, transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(groq_generator.httpx, "AsyncClient", fake_client)


async def _collect(gen: GroqGenerator, command: GeminiGenerationCommand) -> str:
    return "".join([piece async for piece in gen.stream_generate(command)])


@pytest.mark.asyncio
async def test_sends_bearer_key_and_default_model(monkeypatch) -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers["authorization"]
        seen["body"] = request.read().decode()
        return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]})

    _patch_transport(monkeypatch, handler)
    out = await _collect(
        GroqGenerator("k-test"), GeminiGenerationCommand(prompt="질문")
    )

    assert out == "{}"
    assert seen["auth"] == "Bearer k-test"
    assert DEFAULT_GROQ_MODEL in seen["body"]


@pytest.mark.asyncio
async def test_strips_reasoning_block(monkeypatch) -> None:
    content = '<think>고민</think>\n{"pick": "left"}'
    _patch_transport(
        monkeypatch,
        lambda r: httpx.Response(
            200, json={"choices": [{"message": {"content": content}}]}
        ),
    )
    out = await _collect(GroqGenerator("k"), GeminiGenerationCommand(prompt="p"))
    assert out.strip() == '{"pick": "left"}'


@pytest.mark.asyncio
async def test_rate_limit_raises(monkeypatch) -> None:
    _patch_transport(monkeypatch, lambda r: httpx.Response(429, json={}))
    with pytest.raises(httpx.HTTPStatusError):
        await _collect(GroqGenerator("k"), GeminiGenerationCommand(prompt="p"))
