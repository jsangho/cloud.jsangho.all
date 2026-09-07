"""MediaWiki 계보 어댑터 테스트 (Phase 3-13 Stage 1).

두 가지를 고정한다.

1. **`redirects=1`을 보내고, 넘어갔다는 사실을 실어 나른다.** 이것이 없으면 위키는
   리다이렉트 스텁을 요청한 제목 그대로 돌려주고, 제목 대조가 무조건 통과한다.
2. **429는 제한된 횟수만 물러섰다 다시 묻는다.** 실측에서 문서 31개를 연속 조회하다
   8번째에서 429를 맞았다. 무한 재시도도, 예외도 아니다 — 끝내 안 되면 `None`이다.

실제 위키를 부르지 않는다. `httpx.MockTransport`로 응답을 지어낸다.

실행:

    cd fastapi
    PYTHONUTF8=1 PYTHONPATH=apps uv run pytest apps/ontology/tests/wikipedia_revision_metadata_test.py -q
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import httpx
import pytest

from ontology.adapter.outbound.wikipedia_revision_metadata import (
    _MAX_ATTEMPTS,
    _MAX_BACKOFF_SECONDS,
    WikipediaRevisionMetadata,
)

_IYO_SKY_URL = "https://en.wikipedia.org/wiki/IYO_SKY"
_MITB_URL = "https://en.wikipedia.org/wiki/Money_in_the_Bank_(2026)"


def _page_payload(
    *,
    title: str,
    revid: int,
    timestamp: str,
    redirect_from: str | None = None,
) -> dict:
    """실제 MediaWiki 응답 모양. `redirects`는 넘어갔을 때만 실린다."""
    payload: dict = {
        "batchcomplete": True,
        "query": {
            "pages": [
                {
                    "pageid": 1,
                    "ns": 0,
                    "title": title,
                    "revisions": [
                        {"revid": revid, "parentid": revid - 1, "timestamp": timestamp}
                    ],
                }
            ]
        },
    }
    if redirect_from is not None:
        payload["query"]["redirects"] = [{"from": redirect_from, "to": title}]
    return payload


class RecordingSleep:
    """`asyncio.sleep` 자리에 끼워 대기 시간만 기록한다 — 테스트는 안 잔다."""

    def __init__(self) -> None:
        self.waits: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.waits.append(seconds)


def _adapter(
    handler, sleep: RecordingSleep | None = None
) -> tuple[WikipediaRevisionMetadata, RecordingSleep]:
    recorder = sleep or RecordingSleep()
    return (
        WikipediaRevisionMetadata(
            transport=httpx.MockTransport(handler), sleep=recorder
        ),
        recorder,
    )


class TestRedirectsParameter:
    @pytest.mark.asyncio
    async def test_query_sends_redirects_flag(self) -> None:
        """**이 한 줄이 Stage 1의 핵심이다.** 빠지면 스텁이 제목을 위장한다."""
        seen: list[httpx.QueryParams] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request.url.params)
            return httpx.Response(
                200,
                json=_page_payload(
                    title="Money in the Bank (2026)",
                    revid=1367179316,
                    timestamp="2026-08-01T14:24:04Z",
                ),
            )

        adapter, _ = _adapter(handler)
        await adapter.fetch(_MITB_URL)

        assert seen, "요청이 나가야 한다"
        assert seen[0]["redirects"] == "1"
        assert seen[0]["titles"] == "Money in the Bank (2026)"


class TestRedirectIsReported:
    """실측 세 건을 그대로 고정한다."""

    @pytest.mark.asyncio
    async def test_iyo_sky_redirect_is_flagged(self) -> None:
        """**제목이 대소문자만 다르다.** 플래그가 없으면 아무도 못 잡는다."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json=_page_payload(
                    title="Iyo Sky",
                    revid=1141484684,
                    timestamp="2023-02-25T08:31:23Z",
                    redirect_from="IYO SKY",
                ),
            )

        adapter, _ = _adapter(handler)
        revision = await adapter.fetch(_IYO_SKY_URL)

        assert revision is not None
        assert revision.is_redirect is True
        assert revision.title == "Iyo Sky"
        assert revision.revision_id == "1141484684"

    @pytest.mark.asyncio
    async def test_plain_page_is_not_flagged(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json=_page_payload(
                    title="Money in the Bank (2026)",
                    revid=1367179316,
                    timestamp="2026-08-01T14:24:04Z",
                ),
            )

        adapter, _ = _adapter(handler)
        revision = await adapter.fetch(_MITB_URL)

        assert revision is not None
        assert revision.is_redirect is False
        assert revision.revised_at == datetime(2026, 8, 1, 14, 24, 4, tzinfo=UTC)


class TestRateLimitBackoff:
    @pytest.mark.asyncio
    async def test_recovers_after_429(self) -> None:
        """**429 뒤에도 복구된다** — 이게 안 되면 재수집이 계보를 통째로 잃는다."""
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            if calls["n"] < 3:
                return httpx.Response(429, text="rate limited")
            return httpx.Response(
                200,
                json=_page_payload(
                    title="Money in the Bank (2026)",
                    revid=1367179316,
                    timestamp="2026-08-01T14:24:04Z",
                ),
            )

        adapter, sleep = _adapter(handler)
        revision = await adapter.fetch(_MITB_URL)

        assert revision is not None, "제한된 재시도로 복구되어야 한다"
        assert revision.revision_id == "1367179316"
        assert calls["n"] == 3
        assert sleep.waits == [1.0, 2.0], "지수적으로 물러선다"

    @pytest.mark.asyncio
    async def test_gives_up_after_max_attempts(self) -> None:
        """**무한 재시도 금지.** 끝내 안 되면 예외가 아니라 `None`이다."""
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return httpx.Response(429)

        adapter, sleep = _adapter(handler)
        revision = await adapter.fetch(_MITB_URL)

        assert revision is None
        assert calls["n"] == _MAX_ATTEMPTS
        assert len(sleep.waits) == _MAX_ATTEMPTS - 1, "마지막 실패 뒤에는 안 잔다"

    @pytest.mark.asyncio
    async def test_retry_after_header_is_honoured_and_capped(self) -> None:
        """상대가 시킨 값을 따르되, 적재 전체를 몇 분씩 세워 두지는 않는다."""
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            if calls["n"] == 1:
                return httpx.Response(429, headers={"Retry-After": "3"})
            if calls["n"] == 2:
                return httpx.Response(429, headers={"Retry-After": "600"})
            return httpx.Response(
                200,
                json=_page_payload(
                    title="Money in the Bank (2026)",
                    revid=1367179316,
                    timestamp="2026-08-01T14:24:04Z",
                ),
            )

        adapter, sleep = _adapter(handler)
        revision = await adapter.fetch(_MITB_URL)

        assert revision is not None
        assert sleep.waits == [3.0, _MAX_BACKOFF_SECONDS]

    @pytest.mark.asyncio
    async def test_unreadable_retry_after_falls_back_to_backoff(self) -> None:
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            if calls["n"] == 1:
                return httpx.Response(
                    429, headers={"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"}
                )
            return httpx.Response(
                200,
                json=_page_payload(
                    title="Money in the Bank (2026)",
                    revid=1367179316,
                    timestamp="2026-08-01T14:24:04Z",
                ),
            )

        adapter, sleep = _adapter(handler)
        revision = await adapter.fetch(_MITB_URL)

        assert revision is not None
        assert sleep.waits == [1.0]


class TestOtherFailuresAreSwallowed:
    """포트 계약: **모르면 `None`. 예외를 던져 수집을 멈추지 않는다.**"""

    @pytest.mark.asyncio
    async def test_transport_error_returns_none(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("boom")

        adapter, sleep = _adapter(handler)
        assert await adapter.fetch(_MITB_URL) is None
        assert sleep.waits == [], "네트워크 오류는 재시도 대상이 아니다"

    @pytest.mark.asyncio
    async def test_non_200_is_not_retried(self) -> None:
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return httpx.Response(500)

        adapter, _ = _adapter(handler)
        assert await adapter.fetch(_MITB_URL) is None
        assert calls["n"] == 1, "429가 아닌 실패는 물러설 이유가 없다"

    @pytest.mark.asyncio
    async def test_invalid_json_returns_none(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="not json")

        adapter, _ = _adapter(handler)
        assert await adapter.fetch(_MITB_URL) is None

    @pytest.mark.asyncio
    async def test_missing_page_returns_none(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                content=json.dumps(
                    {"query": {"pages": [{"title": "Nope", "missing": True}]}}
                ),
                headers={"content-type": "application/json"},
            )

        adapter, _ = _adapter(handler)
        assert await adapter.fetch(_MITB_URL) is None

    @pytest.mark.asyncio
    async def test_non_wikipedia_host_is_not_called(self) -> None:
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return httpx.Response(200, json={})

        adapter, _ = _adapter(handler)
        assert await adapter.fetch("https://www.wwe.com/shows/summerslam") is None
        assert calls["n"] == 0, "위키가 아니면 요청조차 보내지 않는다"
