"""`action=parse`로 목차와 절 본문을 읽는 어댑터.

**`action=parse`를 쓰는 이유는 `revid`가 같은 응답에 실려 오기 때문이다.** 본문과
개정본이 한 응답에서 나오면 "다른 문서를 가리킬" 수 없다 — `FetchedPage`가 계보를
자기 응답 헤더에서 얻기로 한 것과 같은 이유다. `prop=revisions`로 따로 물으면 그
사이에 문서가 편집될 수 있고, 그때 우리가 적는 계보는 우리가 읽은 본문의 것이 아니다.

**429는 물러섰다가 다시 묻는다.** `wikipedia_revision_metadata`와 같은 대응이고, 이유도
같다 — 에이전트는 경기 수만큼 이 API를 두드리므로 한 번의 429로 실행 전체가 막힌다.
다만 상한은 그쪽보다 낮다. 여기서 막히면 그 경기 하나가 보류로 끝날 뿐이고, 보류는
정상 종료이기 때문이다.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

import httpx

from ontology.app.ports.output.wiki_article_port import (
    WikiArticlePort,
    WikiSection,
    WikiSectionText,
    reduce_markup,
)

logger = logging.getLogger("uvicorn.error")

_API = "https://en.wikipedia.org/w/api.php"
_USER_AGENT = "jsangho-ontology-crawler/1.0"
_TIMEOUT_SECONDS = 20.0

#: 429를 맞았을 때 다시 묻는 횟수의 상한(최초 요청 포함).
_MAX_ATTEMPTS = 3
_INITIAL_BACKOFF_SECONDS = 1.0
_MAX_BACKOFF_SECONDS = 8.0


class WikipediaArticleReader(WikiArticlePort):
    """`transport`·`sleep`은 테스트가 갈아 끼우는 자리다 — 기본값이 실제 동작이다."""

    def __init__(
        self,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Callable[[float], Awaitable[None]] | None = None,
    ) -> None:
        self._transport = transport
        self._sleep = sleep or asyncio.sleep

    async def sections(self, title: str) -> tuple[WikiSection, ...] | None:
        payload = await self._parse(
            {"page": title, "prop": "sections", "redirects": "1"}
        )
        if payload is None:
            return None
        rows = payload.get("sections")
        if not isinstance(rows, list):
            return None

        found: list[WikiSection] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            index = str(row.get("index", "")).strip()
            line = str(row.get("line", "")).strip()
            if not index or not line:
                # 번호 없는 절(`index=""`)은 `action=parse`가 읽어 줄 수 없다.
                continue
            found.append(
                WikiSection(index=index, line=line, level=_int(row.get("level"), 2))
            )
        return tuple(found)

    async def read_section(self, title: str, index: str) -> WikiSectionText | None:
        payload = await self._parse(
            {
                "page": title,
                # **`revid`를 명시해야 실려 온다.** `prop=wikitext`만 보내면 응답에
                # `revid` 키가 아예 없고(실측 2026-09-28), 그러면 계보 없이 본문만
                # 오므로 "같은 응답에서 얻는다"는 이 어댑터의 이유가 조용히 사라진다.
                "prop": "wikitext|revid",
                "section": index,
                "redirects": "1",
            }
        )
        if payload is None:
            return None
        raw = _wikitext(payload)
        if raw is None:
            return None

        revid = payload.get("revid")
        return WikiSectionText(
            # 리다이렉트를 따라간 뒤의 정규 제목. 없으면 물어본 이름을 그대로 쓴다.
            title=str(payload.get("title") or title),
            index=index,
            line=_heading(raw),
            text=reduce_markup(raw),
            revision_id=str(revid) if revid else None,
        )

    async def _parse(self, params: dict[str, str]) -> dict | None:
        """`action=parse` 한 번. **끝내 안 되면 `None`이지 예외가 아니다.**

        없는 문서·없는 절은 `error`로 돌아온다. 그것은 실패가 아니라 답이므로 같은
        `None`으로 옮기고, 부르는 쪽이 "모른다"로 다룬다.
        """
        query = {"action": "parse", "format": "json", "formatversion": "2", **params}
        wait = _INITIAL_BACKOFF_SECONDS

        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                async with httpx.AsyncClient(
                    timeout=_TIMEOUT_SECONDS, transport=self._transport
                ) as client:
                    response = await client.get(
                        _API, params=query, headers={"User-Agent": _USER_AGENT}
                    )

                if response.status_code == 429:
                    if attempt == _MAX_ATTEMPTS:
                        logger.warning(
                            "[ontology.wiki_article] 429 — %d회 시도 후 포기 | page=%s",
                            attempt,
                            params.get("page"),
                        )
                        return None
                    pause = min(wait, _MAX_BACKOFF_SECONDS)
                    logger.info(
                        "[ontology.wiki_article] 429 — %.1fs 뒤 재시도 (%d/%d)",
                        pause,
                        attempt,
                        _MAX_ATTEMPTS,
                    )
                    await self._sleep(pause)
                    wait *= 2
                    continue

                response.raise_for_status()
                payload = response.json()
            except (httpx.HTTPError, ValueError) as exc:
                logger.warning(
                    "[ontology.wiki_article] 조회 실패 | page=%s | %r",
                    params.get("page"),
                    exc,
                )
                return None

            if not isinstance(payload, dict) or "error" in payload:
                logger.info(
                    "[ontology.wiki_article] 응답에 본문이 없습니다 | page=%s",
                    params.get("page"),
                )
                return None
            parsed = payload.get("parse")
            return parsed if isinstance(parsed, dict) else None

        return None


def _wikitext(payload: dict) -> str | None:
    """`parse.wikitext`를 꺼낸다. **판올림마다 모양이 다르다.**

        formatversion=2   "wikitext": "== Results ==\\n..."      ← 우리가 보내는 것
        formatversion=1   "wikitext": {"*": "== Results ==..."}

    실측(2026-09-28 `SummerSlam (2026)` 18번 절)에서 문자열로 왔다. 둘 다 받는 이유는
    `formatversion`을 한 글자 고치는 것이 조용한 사고가 되지 않게 하려는 것이다 —
    `sections`는 두 판올림에서 모양이 같아서, 이 칸만 어긋나면 목차는 되고 본문만
    빈다.
    """
    raw = payload.get("wikitext")
    if isinstance(raw, str):
        return raw
    if isinstance(raw, dict):
        legacy = raw.get("*")
        return legacy if isinstance(legacy, str) else None
    return None


def _int(value: object, default: int) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return default


def _heading(wikitext: str) -> str:
    """절 본문 첫 줄의 `== 제목 ==`에서 제목만 꺼낸다. 없으면 빈 문자열."""
    first = wikitext.lstrip().split("\n", 1)[0].strip()
    stripped = first.strip("=").strip()
    return stripped if first.startswith("=") and stripped else ""
