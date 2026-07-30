"""스트림 가드 테스트 — 스트림 시작 전 실패는 상태 코드로, 시작 후 실패는 본문으로.

실행 (반드시 `fastapi/` 안에서, importlib 임포트 모드로):

    cd fastapi
    PYTHONUTF8=1 PYTHONPATH=. uv run pytest core/tests --import-mode=importlib

저장소 루트에서 실행하거나 기본 임포트 모드를 쓰면 루트의 `fastapi/` 디렉터리가 실제
FastAPI 패키지를 가려 수집 단계에서 ImportError가 난다. 배경은 `core/tests/conftest.py`.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import pytest
from core.matrix.grid_sentinel_stream_guard import (
    EMPTY_UPSTREAM_DETAIL,
    MID_STREAM_NOTICE,
    UPSTREAM_FAILED_DETAIL,
    open_guarded_text_stream,
)
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient

from fastapi import FastAPI, HTTPException


class FakeUpstreamError(Exception):
    """google-genai `APIError` 흉내 — 상태 코드를 `code` 로 들고 있다."""

    def __init__(self, code: int) -> None:
        super().__init__(f"upstream {code}")
        self.code = code


async def _drain(response: StreamingResponse) -> str:
    chunks = [chunk async for chunk in response.body_iterator]
    return "".join(
        chunk.decode() if isinstance(chunk, bytes) else str(chunk) for chunk in chunks
    )


async def _yields(*chunks: str) -> AsyncIterator[str]:
    for chunk in chunks:
        yield chunk


async def _empty() -> AsyncIterator[str]:
    return
    yield  # pragma: no cover — 제너레이터로 만들기 위한 unreachable yield


async def _fails_immediately(exc: BaseException) -> AsyncIterator[str]:
    raise exc
    yield  # pragma: no cover


# CancelledError(BaseException) 도 넣어 보므로 Exception 이 아니라 BaseException 을 받는다.
async def _fails_midway(exc: BaseException) -> AsyncIterator[str]:
    yield "머니볼: 분석해 보면"
    raise exc


class TestHappyPath:
    def test_all_chunks_reach_the_body(self):
        async def run():
            response = await open_guarded_text_stream(
                _yields("가", "나", "다"), label="test"
            )
            return response.status_code, await _drain(response)

        status, body = asyncio.run(run())
        assert status == 200
        assert body == "가나다"


class TestFailureBeforeFirstChunk:
    """헤더가 나가기 전이므로 상태 코드로 실패를 알릴 수 있다."""

    def test_overloaded_upstream_becomes_503(self):
        async def run():
            await open_guarded_text_stream(
                _fails_immediately(FakeUpstreamError(503)), label="test"
            )

        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(run())
        assert exc_info.value.status_code == 503
        assert exc_info.value.detail == UPSTREAM_FAILED_DETAIL

    def test_unknown_failure_becomes_502(self):
        async def run():
            await open_guarded_text_stream(
                _fails_immediately(RuntimeError("boom")), label="test"
            )

        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(run())
        assert exc_info.value.status_code == 502

    def test_empty_stream_becomes_502(self):
        """이전에는 HTTP 200 + 빈 본문으로 조용히 나갔던 경로."""

        async def run():
            await open_guarded_text_stream(_empty(), label="test")

        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(run())
        assert exc_info.value.status_code == 502
        assert exc_info.value.detail == EMPTY_UPSTREAM_DETAIL


class TestOverAsgi:
    """라우터에 붙였을 때 실제 응답으로 나가는 상태 코드·본문을 확인한다."""

    @staticmethod
    def _client() -> TestClient:
        app = FastAPI()

        @app.post("/ok")
        async def ok():
            return await open_guarded_text_stream(_yields("가", "나"), label="test")

        @app.post("/overloaded")
        async def overloaded():
            return await open_guarded_text_stream(
                _fails_immediately(FakeUpstreamError(503)), label="test"
            )

        @app.post("/truncated")
        async def truncated():
            return await open_guarded_text_stream(
                _fails_midway(FakeUpstreamError(503)), label="test"
            )

        return TestClient(app)

    def test_success_streams_text(self):
        response = self._client().post("/ok")
        assert response.status_code == 200
        assert response.text == "가나"

    def test_upstream_failure_is_a_503_not_an_empty_200(self):
        """고치기 전 동작: HTTP 200 + 빈 본문. 클라이언트가 실패를 알 수 없었다."""
        response = self._client().post("/overloaded")
        assert response.status_code == 503
        assert response.json()["detail"] == UPSTREAM_FAILED_DETAIL

    def test_truncated_stream_carries_the_notice_in_the_body(self):
        """헤더가 이미 나간 뒤라 200 이지만, 본문 끝에 중단 안내가 붙는다."""
        response = self._client().post("/truncated")
        assert response.status_code == 200
        assert response.text.endswith(MID_STREAM_NOTICE)


class TestFailureAfterFirstChunk:
    """헤더가 이미 나갔으므로 본문에 안내 문구를 흘려보내는 것만 가능하다."""

    def test_notice_is_appended_to_partial_body(self):
        async def run():
            response = await open_guarded_text_stream(
                _fails_midway(FakeUpstreamError(503)), label="test"
            )
            return await _drain(response)

        body = asyncio.run(run())
        assert body == "머니볼: 분석해 보면" + MID_STREAM_NOTICE

    def test_client_disconnect_is_not_reported_as_failure(self):
        async def run():
            response = await open_guarded_text_stream(
                _fails_midway(asyncio.CancelledError()), label="test"
            )
            with pytest.raises(asyncio.CancelledError):
                await _drain(response)

        asyncio.run(run())
