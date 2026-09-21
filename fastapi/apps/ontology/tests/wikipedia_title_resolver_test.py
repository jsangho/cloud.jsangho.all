"""이름 확인 어댑터 테스트 (Phase 3-13 Stage 5).

**여기서 고정하는 것은 "빗나간 이름이 조용히 통과하지 않는다"이다.** 실측에서
세 갈래가 나왔고(아래 응답은 실제 API가 돌려준 모양 그대로다), 셋을 구분하지
못하면 동음이의 문서가 근거 자리를 차지한다.

실제 위키를 부르지 않는다. `httpx.MockTransport`로 응답을 지어낸다.

실행:

    cd fastapi
    PYTHONUTF8=1 PYTHONPATH=apps uv run pytest apps/ontology/tests/wikipedia_title_resolver_test.py -q
"""

from __future__ import annotations

import httpx
import pytest

from ontology.adapter.outbound.wikipedia_title_resolver import (
    _BATCH_SIZE,
    WikipediaTitleResolver,
)

#: 2026-09-21 실측 응답. `Penta`·`Paige`는 동음이의이고, `Royce Keys`는
#: `Powerhouse Hobbs`로 넘어가며, 없는 이름은 `missing`으로 돌아온다.
_LIVE_PAYLOAD = {
    "batchcomplete": True,
    "query": {
        "normalized": [
            {"fromencoded": False, "from": "Royce_Keys", "to": "Royce Keys"},
            {"fromencoded": False, "from": "IYO_SKY", "to": "IYO SKY"},
        ],
        "redirects": [
            {"from": "IYO SKY", "to": "Iyo Sky"},
            {"from": "Royce Keys", "to": "Powerhouse Hobbs"},
        ],
        "pages": [
            {"ns": 0, "title": "Nonexistent Wrestler Zzz", "missing": True},
            {
                "pageid": 662419,
                "ns": 0,
                "title": "Penta",
                "pageprops": {"disambiguation": ""},
            },
            {"pageid": 34496660, "ns": 0, "title": "Iyo Sky"},
            {"pageid": 58281396, "ns": 0, "title": "Rhea Ripley"},
            {"pageid": 65498948, "ns": 0, "title": "Powerhouse Hobbs"},
        ],
    },
}

_LIVE_NAMES = [
    "Rhea Ripley",
    "Royce_Keys",
    "IYO_SKY",
    "Penta",
    "Nonexistent Wrestler Zzz",
]


def _resolver(handler) -> WikipediaTitleResolver:
    return WikipediaTitleResolver(transport=httpx.MockTransport(handler))


def _serving(payload: dict, *, seen: list[httpx.QueryParams] | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request.url.params)
        return httpx.Response(200, json=payload)

    return handler


class TestLiveShapes:
    @pytest.mark.asyncio
    async def test_a_plain_name_resolves_to_itself(self) -> None:
        table = await _resolver(_serving(_LIVE_PAYLOAD)).resolve(_LIVE_NAMES)

        assert table is not None
        entry = table["Rhea Ripley"]
        assert entry.canonical == "Rhea Ripley"
        assert entry.is_usable
        assert not entry.is_renamed

    @pytest.mark.asyncio
    async def test_a_redirect_reports_the_destination(self) -> None:
        """**본문은 맞고 주소만 어긋나는 경우다.** 정규 제목을 돌려줘야 한다."""
        table = await _resolver(_serving(_LIVE_PAYLOAD)).resolve(_LIVE_NAMES)

        assert table is not None
        entry = table["Royce_Keys"]
        assert entry.canonical == "Powerhouse Hobbs"
        assert entry.is_usable
        assert entry.is_renamed

    @pytest.mark.asyncio
    async def test_a_case_only_redirect_is_still_a_rename(self) -> None:
        """`IYO SKY` → `Iyo Sky`. 대소문자만 달라도 주소는 다른 자리다."""
        table = await _resolver(_serving(_LIVE_PAYLOAD)).resolve(_LIVE_NAMES)

        assert table is not None
        entry = table["IYO_SKY"]
        assert entry.canonical == "Iyo Sky"
        assert entry.is_renamed

    @pytest.mark.asyncio
    async def test_a_disambiguation_page_is_not_usable(self) -> None:
        """**이 테스트가 Stage 5의 핵심이다.** 200으로 돌아오지만 본문이 아니다."""
        table = await _resolver(_serving(_LIVE_PAYLOAD)).resolve(_LIVE_NAMES)

        assert table is not None
        entry = table["Penta"]
        assert entry.canonical == "Penta"
        assert entry.is_disambiguation
        assert not entry.is_usable

    @pytest.mark.asyncio
    async def test_a_missing_page_has_no_canonical_title(self) -> None:
        table = await _resolver(_serving(_LIVE_PAYLOAD)).resolve(_LIVE_NAMES)

        assert table is not None
        entry = table["Nonexistent Wrestler Zzz"]
        assert entry.canonical is None
        assert not entry.is_usable
        assert not entry.is_renamed


class TestRequestShape:
    @pytest.mark.asyncio
    async def test_all_names_go_in_one_request(self) -> None:
        """문서마다 따로 물으면 계보 조회와 같은 429를 스스로 부른다."""
        seen: list[httpx.QueryParams] = []

        table = await _resolver(_serving(_LIVE_PAYLOAD, seen=seen)).resolve(_LIVE_NAMES)

        assert table is not None
        assert len(seen) == 1
        assert seen[0]["titles"] == "|".join(_LIVE_NAMES)

    @pytest.mark.asyncio
    async def test_the_query_asks_for_redirects_and_disambiguation(self) -> None:
        """둘 중 하나라도 빠지면 이 어댑터가 가려야 할 것을 못 가린다."""
        seen: list[httpx.QueryParams] = []

        await _resolver(_serving(_LIVE_PAYLOAD, seen=seen)).resolve(["Penta"])

        assert seen[0]["redirects"] == "1"
        assert seen[0]["ppprop"] == "disambiguation"

    @pytest.mark.asyncio
    async def test_long_lists_are_split_into_batches(self) -> None:
        """`titles` 상한을 넘기면 나머지가 **조용히 잘린다.**"""
        names = [f"Wrestler {i}" for i in range(_BATCH_SIZE + 3)]
        payload = {
            "query": {
                "pages": [{"pageid": i, "title": name} for i, name in enumerate(names)]
            }
        }
        seen: list[httpx.QueryParams] = []

        table = await _resolver(_serving(payload, seen=seen)).resolve(names)

        assert table is not None
        assert len(seen) == 2
        assert len(seen[0]["titles"].split("|")) == _BATCH_SIZE
        assert len(table) == len(names)

    @pytest.mark.asyncio
    async def test_an_empty_list_asks_nothing(self) -> None:
        seen: list[httpx.QueryParams] = []

        table = await _resolver(_serving(_LIVE_PAYLOAD, seen=seen)).resolve([])

        assert table == {}
        assert seen == []


class TestFailureIsNotAGuess:
    @pytest.mark.asyncio
    async def test_a_rate_limit_gives_none_not_a_partial_table(self) -> None:
        """**429에 물러섰다 다시 묻지 않는다.** 부르는 쪽이 멈추는 것이 맞다."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, headers={"Retry-After": "5"})

        assert await _resolver(handler).resolve(["Penta"]) is None

    @pytest.mark.asyncio
    async def test_a_transport_error_gives_none(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("끊김")

        assert await _resolver(handler).resolve(["Penta"]) is None

    @pytest.mark.asyncio
    async def test_a_failed_batch_discards_the_whole_table(self) -> None:
        """절반만 확인된 목록으로 이어가면 나머지 절반이 옛 사고를 그대로 낸다."""
        names = [f"Wrestler {i}" for i in range(_BATCH_SIZE + 3)]
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            if calls["n"] == 1:
                return httpx.Response(
                    200,
                    json={
                        "query": {
                            "pages": [
                                {"pageid": 1, "title": name}
                                for name in names[:_BATCH_SIZE]
                            ]
                        }
                    },
                )
            return httpx.Response(500)

        assert await _resolver(handler).resolve(names) is None
