"""회차 확인 어댑터 테스트 (Phase 3-13 Stage 7).

**여기서 고정하는 것은 "총론이 회차인 척 통과하지 않는다"이다.** 아래 응답은
2026-09-22에 실제 API가 돌려준 모양 그대로다 — 총론이 연도를 갖는다는 사실과,
그 연도가 카테고리 **끝**에 온다는 사실이 이 어댑터 설계의 전부다.

실제 위키를 부르지 않는다. `httpx.MockTransport`로 응답을 지어낸다.

실행:

    cd fastapi
    PYTHONUTF8=1 PYTHONPATH=apps uv run pytest apps/ontology/tests/wikipedia_edition_resolver_test.py -q
"""

from __future__ import annotations

import httpx
import pytest

from ontology.adapter.outbound.wikipedia_edition_resolver import (
    _BATCH_SIZE,
    WikipediaEditionResolver,
)

#: 2026-09-22 실측 응답. 총론 둘(`Royal Rumble`·`WWE Bad Blood`)과 회차 둘
#: (`Royal Rumble (2026)`·`Survivor Series: WarGames (2026)`)이 함께 들어 있다.
_LIVE_PAYLOAD = {
    "batchcomplete": True,
    "query": {
        "redirects": [
            {"from": "Survivor Series (2026)", "to": "Survivor Series: WarGames (2026)"}
        ],
        "pages": [
            {
                "pageid": 518916,
                "ns": 0,
                "title": "Royal Rumble",
                "categories": [
                    {
                        "ns": 14,
                        "title": "Category:Recurring events established in 1988",
                    },
                    {"ns": 14, "title": "Category:Royal Rumble"},
                ],
            },
            {
                "pageid": 1217510,
                "ns": 0,
                "title": "WWE Bad Blood",
                "categories": [
                    {
                        "ns": 14,
                        "title": "Category:Recurring events disestablished in 2004",
                    },
                    {
                        "ns": 14,
                        "title": "Category:Recurring events established in 1997",
                    },
                    {"ns": 14, "title": "Category:WWE Bad Blood"},
                ],
            },
            {
                "pageid": 77543311,
                "ns": 0,
                "title": "Royal Rumble (2026)",
                "categories": [
                    {"ns": 14, "title": "Category:2026 WWE Network events"},
                    {"ns": 14, "title": "Category:2026 WWE pay-per-view events"},
                    {"ns": 14, "title": "Category:January 2026 in Saudi Arabia"},
                    {"ns": 14, "title": "Category:Royal Rumble"},
                ],
            },
            {
                "pageid": 83683496,
                "ns": 0,
                "title": "Survivor Series: WarGames (2026)",
                "categories": [
                    {"ns": 14, "title": "Category:2026 WWE Network events"},
                    {"ns": 14, "title": "Category:2026 in Houston"},
                    {"ns": 14, "title": "Category:November 2026 in the United States"},
                    {"ns": 14, "title": "Category:Survivor Series"},
                ],
            },
            {"ns": 0, "title": "Bad Blood (2026)", "missing": True},
        ],
    },
}

_LIVE_TITLES = [
    "Royal Rumble",
    "Royal Rumble (2026)",
    "Survivor Series (2026)",
    "WWE Bad Blood",
    "Bad Blood (2026)",
]


def _resolver(handler) -> WikipediaEditionResolver:
    return WikipediaEditionResolver(transport=httpx.MockTransport(handler))


def _serving(payload: dict, *, seen: list[httpx.QueryParams] | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request.url.params)
        return httpx.Response(200, json=payload)

    return handler


class TestLiveShapes:
    @pytest.mark.asyncio
    async def test_an_edition_article_covers_its_year(self) -> None:
        table = await _resolver(_serving(_LIVE_PAYLOAD)).editions(_LIVE_TITLES)

        assert table is not None
        assert table["Royal Rumble (2026)"].covers(2026)

    @pytest.mark.asyncio
    async def test_an_overview_article_covers_no_year(self) -> None:
        """**이 테스트가 Stage 7의 핵심이다.** 총론은 실재하고 200으로 돌아온다."""
        table = await _resolver(_serving(_LIVE_PAYLOAD)).editions(_LIVE_TITLES)

        assert table is not None
        assert not table["Royal Rumble"].covers(2026)

    @pytest.mark.asyncio
    async def test_the_founding_year_of_a_series_is_not_an_edition(self) -> None:
        """`Recurring events established in 1988`의 1988은 회차가 아니다.

        연도를 **포함**으로 읽으면 그해 창설된 대회의 총론이 통과한다. 그래서
        맨 앞에 놓인 연도만 센다.
        """
        table = await _resolver(_serving(_LIVE_PAYLOAD)).editions(_LIVE_TITLES)

        assert table is not None
        assert table["Royal Rumble"].years == frozenset()
        assert not table["WWE Bad Blood"].covers(1997)
        assert not table["WWE Bad Blood"].covers(2004)

    @pytest.mark.asyncio
    async def test_a_redirect_is_judged_at_its_destination(self) -> None:
        """`Survivor Series (2026)` → `Survivor Series: WarGames (2026)`.

        목적지를 안 따라가면 스텁의 카테고리(0건)를 읽어 **거짓 거부**가 난다.
        """
        table = await _resolver(_serving(_LIVE_PAYLOAD)).editions(_LIVE_TITLES)

        assert table is not None
        assert table["Survivor Series (2026)"].covers(2026)

    @pytest.mark.asyncio
    async def test_a_month_qualified_category_is_not_a_leading_year(self) -> None:
        """`January 2026 in Saudi Arabia`는 세지 않는다 — 같은 문서의 다른
        카테고리가 이미 2026을 대고 있으므로 판정은 그대로다."""
        table = await _resolver(_serving(_LIVE_PAYLOAD)).editions(_LIVE_TITLES)

        assert table is not None
        assert table["Royal Rumble (2026)"].years == frozenset({2026})

    @pytest.mark.asyncio
    async def test_a_missing_page_covers_no_year(self) -> None:
        table = await _resolver(_serving(_LIVE_PAYLOAD)).editions(_LIVE_TITLES)

        assert table is not None
        assert table["Bad Blood (2026)"].years == frozenset()

    @pytest.mark.asyncio
    async def test_the_wrong_edition_is_told_apart(self) -> None:
        """엉뚱한 회차는 자기 해만 덮는다 — 총론과는 다른 이유로 거부된다."""
        payload = {
            "query": {
                "pages": [
                    {
                        "pageid": 1,
                        "title": "Royal Rumble (2025)",
                        "categories": [
                            {"ns": 14, "title": "Category:2025 WWE Network events"}
                        ],
                    }
                ]
            }
        }

        table = await _resolver(_serving(payload)).editions(["Royal Rumble (2025)"])

        assert table is not None
        assert table["Royal Rumble (2025)"].covers(2025)
        assert not table["Royal Rumble (2025)"].covers(2026)


class TestRequestShape:
    @pytest.mark.asyncio
    async def test_the_query_asks_for_visible_categories_and_redirects(self) -> None:
        """넷 중 하나라도 빠지면 판정이 틀어진다 — 숨은 카테고리는 상한만 먹고,
        리다이렉트를 안 따라가면 스텁을 읽는다."""
        seen: list[httpx.QueryParams] = []

        await _resolver(_serving(_LIVE_PAYLOAD, seen=seen)).editions(["Royal Rumble"])

        assert seen[0]["prop"] == "categories"
        assert seen[0]["redirects"] == "1"
        assert seen[0]["cllimit"] == "max"
        assert seen[0]["clshow"] == "!hidden"

    @pytest.mark.asyncio
    async def test_all_titles_go_in_one_request(self) -> None:
        seen: list[httpx.QueryParams] = []

        table = await _resolver(_serving(_LIVE_PAYLOAD, seen=seen)).editions(
            _LIVE_TITLES
        )

        assert table is not None
        assert len(seen) == 1

    @pytest.mark.asyncio
    async def test_an_empty_list_asks_nothing(self) -> None:
        seen: list[httpx.QueryParams] = []

        table = await _resolver(_serving(_LIVE_PAYLOAD, seen=seen)).editions([])

        assert table == {}
        assert seen == []

    @pytest.mark.asyncio
    async def test_long_lists_are_split_into_batches(self) -> None:
        titles = [f"Event {i} (2026)" for i in range(_BATCH_SIZE + 2)]
        payload = {"query": {"pages": [{"pageid": 1, "title": t} for t in titles]}}
        seen: list[httpx.QueryParams] = []

        table = await _resolver(_serving(payload, seen=seen)).editions(titles)

        assert table is not None
        assert len(seen) == 2
        assert len(table) == len(titles)


class TestTruncationIsFailureNotAnAnswer:
    @pytest.mark.asyncio
    async def test_a_continued_response_gives_none(self) -> None:
        """**잘린 카테고리로 판정하면 회차 문서가 거짓 거부된다.**

        빈 집합으로 돌려주는 것이 가장 나쁘다 — 조용히 "회차가 아니다"가 된다.
        """
        payload = {
            "continue": {"clcontinue": "518916|Royal_Rumble", "continue": "||"},
            "query": {"pages": [{"pageid": 518916, "title": "Royal Rumble (2026)"}]},
        }

        assert (
            await _resolver(_serving(payload)).editions(["Royal Rumble (2026)"]) is None
        )

    @pytest.mark.asyncio
    async def test_a_rate_limit_gives_none(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, headers={"Retry-After": "5"})

        assert await _resolver(handler).editions(["Royal Rumble (2026)"]) is None

    @pytest.mark.asyncio
    async def test_a_transport_error_gives_none(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("끊김")

        assert await _resolver(handler).editions(["Royal Rumble (2026)"]) is None

    @pytest.mark.asyncio
    async def test_a_failed_batch_discards_the_whole_table(self) -> None:
        titles = [f"Event {i} (2026)" for i in range(_BATCH_SIZE + 2)]
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            if calls["n"] == 1:
                return httpx.Response(
                    200,
                    json={
                        "query": {
                            "pages": [
                                {"pageid": 1, "title": t} for t in titles[:_BATCH_SIZE]
                            ]
                        }
                    },
                )
            return httpx.Response(500)

        assert await _resolver(handler).editions(titles) is None
