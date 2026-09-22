"""문서가 어느 해 회차인지 MediaWiki 카테고리로 확인하는 어댑터 (Phase 3-13 Stage 7).

`WikipediaTitleResolver`와 같은 `action=query` 엔드포인트를 쓰지만 **묻는 것이
다르다** — 저쪽은 `pageprops`로 문서의 정체를, 이쪽은 `categories`로 문서가 걸린
해를 읽는다. 둘을 한 요청에 합치지 않은 이유가 이 파일의 핵심이다.

## 왜 이름 확인과 같은 요청에 얹지 않는가

`prop=categories`는 문서마다 카테고리를 수십 개씩 싣고 **전체 합계가 500에서
잘린다**(`limits: {categories: 500}`). 이름 확인은 한 번에 50문서를 묻고 선수
문서는 카테고리가 10~20개씩이라, 합치면 상한에 닿는다. 잘리면 회차 문서가
카테고리 0건으로 보여 **거짓 거부**가 난다 — 조용한 오작동이다.

부르는 쪽이 대회 문서 하나만 넘기므로, 따로 두면 그 잘림이 **구조적으로 일어나지
않는다.** 요청이 하나 느는 대신 한 축이 통째로 사라진다.

## 잘림은 답이 아니라 실패다

그래도 만약을 대비해 `continue`가 오면 `None`을 돌려준다. `cllimit=max`에서
`continue`는 "더 있다"는 뜻뿐이고, 그 상태의 `years`는 반쪽이라 판정에 쓸 수 없다.
빈 집합으로 돌려주면 그게 곧 거짓 거부가 된다.

**재시도하지 않는다** — `WikipediaTitleResolver`와 같은 이유다(적재당 요청 한두 건).
"""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence

import httpx

from ontology.app.ports.output.wiki_edition_port import WikiEdition, WikiEditionPort

logger = logging.getLogger("uvicorn.error")

_API = "https://en.wikipedia.org/w/api.php"
_USER_AGENT = "jsangho-ontology-crawler/1.0"
_TIMEOUT_SECONDS = 20.0

#: 대회 문서만 오므로 50까지 갈 일이 없다. 작게 잡아 `cllimit` 상한에서 멀리 둔다.
_BATCH_SIZE = 10

#: **맨 앞의 연도만 센다.** `Recurring events established in 1988`은 총론이 달고
#: 있는 창설 연도라 회차의 근거가 못 된다 (`wiki_edition_port` 독스트링 참조).
_LEADING_YEAR = re.compile(r"^(?:19|20)\d{2}\b")


class WikipediaEditionResolver(WikiEditionPort):
    """`transport`는 테스트가 갈아 끼우는 자리다 — 기본값이 실제 동작이다."""

    def __init__(self, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._transport = transport

    async def editions(self, titles: Sequence[str]) -> dict[str, WikiEdition] | None:
        wanted = [t.strip() for t in titles if t and t.strip()]
        if not wanted:
            return {}

        table: dict[str, WikiEdition] = {}
        for start in range(0, len(wanted), _BATCH_SIZE):
            batch = wanted[start : start + _BATCH_SIZE]
            payload = await self._query(batch)
            if payload is None:
                return None
            table.update(_read(batch, payload))
        return table

    async def _query(self, titles: Sequence[str]) -> dict | None:
        params = {
            "action": "query",
            "format": "json",
            "formatversion": "2",
            # 넘겨받은 제목은 이미 정규 제목이지만, 리다이렉트를 안 따라가면
            # 스텁의 카테고리(대개 0건)를 읽어 거짓 거부가 난다.
            "redirects": "1",
            "prop": "categories",
            "cllimit": "max",
            # 숨은 유지보수 카테고리(`Articles with short description` 등)는
            # 연도를 갖지 않으면서 상한만 먹는다.
            "clshow": "!hidden",
            "titles": "|".join(titles),
        }
        try:
            async with httpx.AsyncClient(
                timeout=_TIMEOUT_SECONDS,
                follow_redirects=True,
                transport=self._transport,
            ) as client:
                response = await client.get(
                    _API, params=params, headers={"User-Agent": _USER_AGENT}
                )
            if response.status_code != 200:
                logger.warning(
                    "[ontology.wiki_edition] 조회 실패 | status=%s | 제목=%d건",
                    response.status_code,
                    len(titles),
                )
                return None
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("[ontology.wiki_edition] 조회 실패 | %s", exc)
            return None

        if "continue" in payload:
            # 반쪽짜리 카테고리 목록으로 판정하면 회차 문서가 거짓 거부된다.
            logger.warning(
                "[ontology.wiki_edition] 카테고리가 잘렸다 | 제목=%d건", len(titles)
            )
            return None
        return payload


def _read(requested: Sequence[str], payload: dict) -> dict[str, WikiEdition]:
    query = payload.get("query") or {}
    normalized = _pairs(query.get("normalized"))
    redirects = _pairs(query.get("redirects"))
    pages = {
        str(page.get("title")): page
        for page in (query.get("pages") or [])
        if page.get("title")
    }

    table: dict[str, WikiEdition] = {}
    for name in requested:
        page = pages.get(_follow(name, normalized, redirects))
        table[name] = WikiEdition(title=name, years=_years(page))
    return table


def _years(page: dict | None) -> frozenset[int]:
    """카테고리 **맨 앞**에 놓인 연도만 모은다. 없는 문서는 빈 집합이다."""
    if page is None or page.get("missing") or page.get("invalid"):
        return frozenset()
    found: set[int] = set()
    for entry in page.get("categories") or []:
        title = str(entry.get("title") or "").removeprefix("Category:")
        match = _LEADING_YEAR.match(title)
        if match is not None:
            found.add(int(match.group()))
    return frozenset(found)


def _pairs(entries: object) -> dict[str, str]:
    if not isinstance(entries, list):
        return {}
    return {
        str(entry["from"]): str(entry["to"])
        for entry in entries
        if isinstance(entry, dict) and entry.get("from") and entry.get("to")
    }


def _follow(name: str, normalized: dict[str, str], redirects: dict[str, str]) -> str:
    """물어본 제목에서 실제 문서 제목까지 따라간다.

    `WikipediaTitleResolver._follow`와 같은 모양이다 — 순환 리다이렉트에서 멈추는
    것까지 같다. 두 어댑터가 같은 응답 구조를 각자 읽으므로 공유하지 않는다.
    """
    title = normalized.get(name, name)
    seen = {title}
    while title in redirects:
        title = redirects[title]
        if title in seen:
            break
        seen.add(title)
    return title
