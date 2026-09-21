"""이름이 가리키는 위키 문서를 MediaWiki API로 확인하는 어댑터 (Phase 3-13 Stage 5).

**한 번의 요청으로 이름 전부를 묻는다.** `titles=A|B|C`로 최대 50개씩 묶이고,
응답 하나에 세 가지 사실이 함께 실린다.

    query.normalized   보낸 문자열 → 위키 표기    (`IYO_SKY` → `IYO SKY`)
    query.redirects    표기 → 넘어간 목적지        (`IYO SKY` → `Iyo Sky`)
    query.pages[]      목적지의 정체              `missing` · `pageprops.disambiguation`

그래서 이 어댑터가 하는 일은 그 셋을 **이어 붙여 되짚는 것**이다 — 물어본 이름에서
출발해 정규화와 리다이렉트를 따라가면 실제 문서에 닿는다.

**재시도하지 않는다.** 계보 어댑터(`wikipedia_revision_metadata`)는 문서 수만큼
두드리느라 429를 맞고도 계속 가야 하지만, 이 조회는 적재 한 번에 한두 요청뿐이다.
여기서 429가 났다면 뒤따라올 문서별 본문·계보 요청은 더 심하게 막힌다 — 물러섰다
다시 묻는 것보다 **그 자리에서 멈추고 사람에게 알리는 쪽**이 맞다.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

import httpx

from ontology.app.ports.output.wiki_title_port import WikiTitle, WikiTitlePort

logger = logging.getLogger("uvicorn.error")

_API = "https://en.wikipedia.org/w/api.php"
_USER_AGENT = "jsangho-ontology-crawler/1.0"
_TIMEOUT_SECONDS = 20.0

#: 익명 요청의 `titles` 상한. 넘기면 나머지가 조용히 잘린다.
_BATCH_SIZE = 50


class WikipediaTitleResolver(WikiTitlePort):
    """`transport`는 테스트가 갈아 끼우는 자리다 — 기본값이 실제 동작이다."""

    def __init__(self, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._transport = transport

    async def resolve(self, titles: Sequence[str]) -> dict[str, WikiTitle] | None:
        wanted = [t.strip() for t in titles if t and t.strip()]
        if not wanted:
            return {}

        resolved: dict[str, WikiTitle] = {}
        for start in range(0, len(wanted), _BATCH_SIZE):
            batch = wanted[start : start + _BATCH_SIZE]
            payload = await self._query(batch)
            if payload is None:
                # 한 묶음이라도 못 읽었으면 표 전체가 못 믿을 것이 된다. 절반만
                # 확인된 목록으로 수집을 이어가면 나머지 절반이 옛 사고를 그대로 낸다.
                return None
            resolved.update(_read(batch, payload))
        return resolved

    async def _query(self, titles: Sequence[str]) -> dict | None:
        params = {
            "action": "query",
            "format": "json",
            "formatversion": "2",
            # 리다이렉트를 따라가야 목적지의 정체(동음이의 여부)를 볼 수 있다.
            "redirects": "1",
            "prop": "pageprops",
            # 동음이의 표시 하나만 받는다. 전체 pageprops는 문서마다 수십 줄이다.
            "ppprop": "disambiguation",
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
                    "[ontology.wiki_title] 조회 실패 | status=%s | 이름=%d건",
                    response.status_code,
                    len(titles),
                )
                return None
            return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("[ontology.wiki_title] 조회 실패 | %s", exc)
            return None


def _read(requested: Sequence[str], payload: dict) -> dict[str, WikiTitle]:
    query = payload.get("query") or {}
    normalized = _pairs(query.get("normalized"))
    redirects = _pairs(query.get("redirects"))
    pages = {
        str(page.get("title")): page
        for page in (query.get("pages") or [])
        if page.get("title")
    }

    table: dict[str, WikiTitle] = {}
    for name in requested:
        destination = _follow(name, normalized, redirects)
        page = pages.get(destination)
        if page is None or page.get("missing") or page.get("invalid"):
            table[name] = WikiTitle(requested=name, canonical=None)
            continue
        table[name] = WikiTitle(
            requested=name,
            canonical=str(page.get("title")),
            is_disambiguation="disambiguation" in (page.get("pageprops") or {}),
        )
    return table


def _pairs(entries: object) -> dict[str, str]:
    if not isinstance(entries, list):
        return {}
    return {
        str(entry["from"]): str(entry["to"])
        for entry in entries
        if isinstance(entry, dict) and entry.get("from") and entry.get("to")
    }


def _follow(name: str, normalized: dict[str, str], redirects: dict[str, str]) -> str:
    """물어본 이름에서 실제 문서 제목까지 따라간다.

    리다이렉트가 여러 칸 이어질 수 있어 반복해서 따라가되, **자기 자신으로 돌아오면
    거기서 멈춘다.** 위키에 순환 리다이렉트가 있으면 여기가 무한 루프가 된다.
    """
    title = normalized.get(name, name)
    seen = {title}
    while title in redirects:
        title = redirects[title]
        if title in seen:
            break
        seen.add(title)
    return title
