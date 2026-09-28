"""문서 목차·절 본문 어댑터와 마크업 줄이기 테스트.

세 가지를 고정한다.

1. **`revid`를 본문과 같은 응답에서 얻는다.** 계보를 따로 물으면 그 사이의 편집이
   우리가 읽은 본문과 다른 판본을 가리킬 수 있다.
2. **표를 버리지 않는다.** 대회 결과가 `{| class="wikitable"` 안에 있어서, 여기서
   표를 지우면 정작 찾는 사실이 사라진다.
3. **없는 문서·없는 절은 `None`이지 예외가 아니다.** 부르는 쪽이 "모른다"로 다룬다.

실제 위키를 부르지 않는다. `httpx.MockTransport`로 응답을 지어낸다.

실행:

    cd fastapi
    PYTHONUTF8=1 PYTHONPATH=apps uv run pytest apps/ontology/tests/wikipedia_article_reader_test.py -q
"""

from __future__ import annotations

import json

import httpx
import pytest

from ontology.adapter.outbound.wikipedia_article_reader import (
    _MAX_ATTEMPTS,
    WikipediaArticleReader,
)
from ontology.app.ports.output.wiki_article_port import reduce_markup

_TITLE = "SummerSlam (2026)"

_RESULTS_WIKITEXT = (
    "== Results ==\n"
    '{| class="wikitable"\n'
    "! No. !! Results !! Stipulation\n"
    "|-\n"
    "| 1 || '''[[Roman Reigns]]''' defeated [[Cody Rhodes]]<ref name=\"a\">"
    "Some citation</ref> || Singles match\n"
    "|}"
)


def _reader(handler, *, sleeps: list[float] | None = None) -> WikipediaArticleReader:
    async def _sleep(seconds: float) -> None:
        (sleeps if sleeps is not None else []).append(seconds)

    return WikipediaArticleReader(transport=httpx.MockTransport(handler), sleep=_sleep)


def _json(payload: dict, status: int = 200) -> httpx.Response:
    return httpx.Response(
        status,
        content=json.dumps(payload),
        headers={"content-type": "application/json"},
    )


class TestReduceMarkup:
    def test_paired_refs_are_removed(self) -> None:
        assert reduce_markup('won<ref name="a">cite</ref> the match') == (
            "won the match"
        )

    def test_self_closing_ref_is_removed(self) -> None:
        assert reduce_markup('won<ref name="a" /> it') == "won it"

    def test_piped_link_keeps_display_name(self) -> None:
        """카드에 적힌 이름이 표시되는 쪽이다."""
        assert reduce_markup("[[Pentagón Jr.|Penta]] won") == "Penta won"

    def test_plain_link_keeps_target(self) -> None:
        assert reduce_markup("[[Rhea Ripley]] won") == "Rhea Ripley won"

    def test_bold_quotes_are_removed(self) -> None:
        """승자 이름이 굵게 적히는 일이 많아, 남기면 이름 대조가 빗나간다."""
        assert reduce_markup("'''Reigns''' defeated ''Rhodes''") == (
            "Reigns defeated Rhodes"
        )

    def test_table_delimiters_are_kept(self) -> None:
        """어느 칸이 승자인지는 표 구조가 말한다."""
        reduced = reduce_markup(_RESULTS_WIKITEXT)

        assert "{|" in reduced
        assert "|-" in reduced
        assert "Roman Reigns" in reduced
        assert "Some citation" not in reduced

    def test_comments_are_removed(self) -> None:
        assert reduce_markup("won <!-- 확인 필요 --> it") == "won  it"


class TestSections:
    @pytest.mark.asyncio
    async def test_sections_are_read(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.params["prop"] == "sections"
            assert request.url.params["redirects"] == "1"
            return _json(
                {
                    "parse": {
                        "title": _TITLE,
                        "sections": [
                            {"index": "1", "line": "Background", "level": "2"},
                            {"index": "3", "line": "Results", "level": "2"},
                        ],
                    }
                }
            )

        sections = await _reader(handler).sections(_TITLE)

        assert sections is not None
        assert [(s.index, s.line) for s in sections] == [
            ("1", "Background"),
            ("3", "Results"),
        ]

    @pytest.mark.asyncio
    async def test_unnumbered_sections_are_skipped(self) -> None:
        """`index=""`인 절은 `action=parse`가 읽어 줄 수 없다."""

        def handler(request: httpx.Request) -> httpx.Response:
            return _json(
                {
                    "parse": {
                        "sections": [
                            {"index": "", "line": "Transcluded", "level": "2"},
                            {"index": "1", "line": "Results", "level": "2"},
                        ]
                    }
                }
            )

        sections = await _reader(handler).sections(_TITLE)

        assert sections is not None
        assert [s.line for s in sections] == ["Results"]

    @pytest.mark.asyncio
    async def test_missing_article_returns_none(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return _json({"error": {"code": "missingtitle"}})

        assert await _reader(handler).sections("없는 대회") is None


class TestReadSection:
    @pytest.mark.asyncio
    async def test_text_and_revid_come_from_one_response(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            # `revid`를 명시하지 않으면 응답에 그 키가 없다 — 계보가 조용히 빈다.
            assert request.url.params["prop"] == "wikitext|revid"
            assert request.url.params["section"] == "3"
            return _json(
                {
                    "parse": {
                        "title": _TITLE,
                        "revid": 1234567,
                        "wikitext": _RESULTS_WIKITEXT,
                    }
                }
            )

        section = await _reader(handler).read_section(_TITLE, "3")

        assert section is not None
        assert section.title == _TITLE
        assert section.revision_id == "1234567"
        assert section.line == "Results"
        assert "Roman Reigns" in section.text
        # 각주는 사라지고 표는 남는다.
        assert "Some citation" not in section.text
        assert "{|" in section.text

    @pytest.mark.asyncio
    async def test_missing_revid_is_not_claimed(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return _json({"parse": {"title": _TITLE, "wikitext": "내용"}})

        section = await _reader(handler).read_section(_TITLE, "1")

        assert section is not None
        assert section.revision_id is None

    @pytest.mark.asyncio
    async def test_legacy_formatversion_shape_is_accepted(self) -> None:
        """`formatversion=1`은 `{"*": ...}`로 싼다.

        우리가 보내는 것은 `2`(문자열)이지만 둘 다 받는다 — 이 칸만 어긋나면 목차는
        되고 본문만 비어서, 실패가 "결과가 안 적힌 문서"처럼 보인다.
        """

        def handler(request: httpx.Request) -> httpx.Response:
            return _json(
                {"parse": {"revid": 5, "wikitext": {"*": "== Results ==\n내용"}}}
            )

        section = await _reader(handler).read_section(_TITLE, "3")

        assert section is not None
        assert section.line == "Results"
        assert "내용" in section.text

    @pytest.mark.asyncio
    async def test_unknown_wikitext_shape_returns_none(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return _json({"parse": {"revid": 5, "wikitext": ["내용"]}})

        assert await _reader(handler).read_section(_TITLE, "3") is None

    @pytest.mark.asyncio
    async def test_missing_section_returns_none(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return _json({"error": {"code": "nosuchsection"}})

        assert await _reader(handler).read_section(_TITLE, "99") is None

    @pytest.mark.asyncio
    async def test_broken_json_returns_none(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=b"<html>not json</html>")

        assert await _reader(handler).read_section(_TITLE, "3") is None


class TestRateLimit:
    @pytest.mark.asyncio
    async def test_429_backs_off_then_asks_again(self) -> None:
        attempts: list[int] = []

        def handler(request: httpx.Request) -> httpx.Response:
            attempts.append(1)
            if len(attempts) < 2:
                return httpx.Response(429)
            return _json({"parse": {"revid": 1, "wikitext": "내용"}})

        sleeps: list[float] = []
        section = await _reader(handler, sleeps=sleeps).read_section(_TITLE, "3")

        assert section is not None
        assert len(attempts) == 2
        assert sleeps == [1.0]

    @pytest.mark.asyncio
    async def test_persistent_429_returns_none_not_raise(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(429)

        assert await _reader(handler).sections(_TITLE) is None
        assert _MAX_ATTEMPTS == 3
