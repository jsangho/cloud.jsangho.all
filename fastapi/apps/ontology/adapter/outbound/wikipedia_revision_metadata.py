"""위키피디아 MediaWiki API로 개정본 계보를 읽는 어댑터 (Phase 3-12).

**왜 HTML이 아니라 API인가.** 위키는 `article:published_time` 계열 메타태그를
내보내지 않아 페이지만 봐서는 시각을 알 수 없다. `Last-Modified` 헤더가 있지만
그것은 `page_touched`라 **개정본 시각이 아니다** — 실측에서 Oba Femi가 최신 개정본
`2026-08-04T18:40:31Z`인데 헤더는 `2026-08-25T20:29:13Z`로 21일이 벌어져 있었다.
템플릿·분류가 바뀌어도 올라가기 때문이다. 그래서 API가 말하는 `revid`/`timestamp`만
계보로 인정한다.

**URL의 `oldid`를 그대로 믿지 않는다.** 잘린 식별자는 에러를 내지 않고 **다른 문서로
조용히 해석된다**(실측: `oldid=13677280` → "Who Framed Roger Rabbit", 2005년).
그래서 이 어댑터는 API가 돌려준 `title`을 함께 담아 보내고, 대조는 부르는 쪽이 한다.

**`redirects=1`을 붙인다** (Phase 3-13 Stage 1). 이것이 없으면 MediaWiki는 리다이렉트
스텁 페이지를 **요청한 제목 그대로** 돌려준다 — 그래서 제목 대조가 무조건 통과하고,
본문 fetch는 리다이렉트를 따라가 **다른 문서**를 가져온다. 둘이 어긋나는 것을 아무도
못 잡는다. 실측된 세 건:

- `/wiki/IYO_SKY` → `Iyo Sky` (스텁 개정본 **2023-02-25**)
- `/wiki/Royce_Keys` → `Powerhouse Hobbs` (스텁 개정본 2026-02-04)
- `/wiki/The_Bloodline` → `Bloodline (disambiguation)`

`redirects=1`을 붙이면 응답의 `query.redirects`가 넘어간 사실을 실토한다. 그 사실을
`RevisionMetadata.is_redirect`로 실어 보내고, 버릴지는 부르는 쪽이 정한다.

**429는 물러섰다가 다시 묻는다.** 익명 요청 한도가 좁아, 실측에서 문서 31개를 0.3초
간격으로 조회하다 **8번째에서 429**를 받고 이후가 전부 막혔다. 재수집은 문서 수만큼
이 API를 두드리므로 한 번의 429로 계보가 통째로 비는 일이 실제로 일어난다. 그래서
제한된 횟수만 지수적으로 물러섰다가 다시 묻는다 — **무한 재시도는 하지 않고**, 끝내
못 얻으면 예외 대신 `None`이다(수집을 멈추지 않는다는 기존 계약).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from urllib.parse import urlparse

import httpx

from ontology.app.ports.output.revision_metadata_port import (
    RevisionMetadata,
    RevisionMetadataPort,
    wiki_title_from_url,
)

logger = logging.getLogger("uvicorn.error")

_API = "https://{host}/w/api.php"
_USER_AGENT = "jsangho-ontology-crawler/1.0"
_TIMEOUT_SECONDS = 20.0

#: 429를 맞았을 때 다시 묻는 횟수의 상한(최초 요청 포함). 넉넉하게 잡을 값이 아니다 —
#: 문서 하나가 오래 붙들고 있으면 뒤의 문서들이 그만큼 늦어진다.
_MAX_ATTEMPTS = 4
#: 첫 대기. 이후 두 배씩 늘어난다 (1s → 2s → 4s).
_INITIAL_BACKOFF_SECONDS = 1.0
#: 한 번의 대기 상한. `Retry-After`가 이보다 길면 여기서 자른다 — 상대가 시킨 값이라도
#: 적재 전체를 몇 분씩 세워 두지는 않는다.
_MAX_BACKOFF_SECONDS = 8.0


def _parse_timestamp(raw: object) -> datetime | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        parsed = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _retry_after_seconds(response: httpx.Response) -> float | None:
    """`Retry-After`를 초로 읽는다. 못 읽으면 `None`이라 기본 백오프로 간다.

    HTTP-date 형식도 규격에 있지만 위키는 초를 준다. 못 읽는 값을 억지로 해석하느니
    기본값으로 물러서는 편이 예측 가능하다.
    """
    raw = response.headers.get("Retry-After")
    if raw is None:
        return None
    try:
        seconds = float(raw.strip())
    except (AttributeError, ValueError):
        return None
    return seconds if seconds >= 0 else None


class WikipediaRevisionMetadata(RevisionMetadataPort):
    """위키 문서 하나의 최신 개정본 계보를 읽는다.

    한 번에 한 문서만 묻는 이유는 부르는 쪽(`PublicSourceInteractor`)이 문서 단위로
    돌기 때문이다. 배치가 필요해지면 `revids=`/`titles=`에 `|`로 이어 붙이면 되는데,
    **`rvlimit`은 다중 문서와 함께 못 쓴다**(`invalidparammix`) — 그때는 `rvlimit`을
    빼야 한다.

    `transport`·`sleep`은 **테스트가 갈아 끼우는 자리**다. 기본값이 실제 동작이라
    운영 경로는 이 인자들을 모른다.
    """

    def __init__(
        self,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Callable[[float], Awaitable[None]] | None = None,
    ) -> None:
        self._transport = transport
        self._sleep = sleep or asyncio.sleep

    async def fetch(self, url: str) -> RevisionMetadata | None:
        title = wiki_title_from_url(url)
        if title is None:
            return None

        host = (urlparse(url).hostname or "").lower()
        if not host.endswith("wikipedia.org"):
            return None

        params = {
            "action": "query",
            "format": "json",
            "formatversion": "2",
            "prop": "revisions",
            "rvprop": "ids|timestamp",
            "titles": title,
            # 리다이렉트를 따라가게 해서 **넘어갔다는 사실 자체를** 응답에 남긴다.
            # 이것이 없으면 스텁이 요청한 제목 그대로 돌아와 대조를 통과한다.
            "redirects": "1",
        }
        payload = await self._query(url, host, params)
        if payload is None:
            return None

        query = payload.get("query", {})
        # 넘어갔으면 `query.redirects`에 (from, to)가 실린다. 목적지 제목이 요청과
        # 대소문자만 다를 수 있으므로 **제목이 아니라 이 목록의 존재**로 판정한다.
        redirects = query.get("redirects") or []
        is_redirect = bool(redirects)
        if is_redirect:
            logger.info(
                "[ontology.revision] 리다이렉트 감지 | url=%s | %s → %s",
                url,
                redirects[0].get("from"),
                redirects[0].get("to"),
            )

        pages = query.get("pages") or []
        if not pages:
            return None
        page = pages[0]
        if page.get("missing"):
            return None
        revisions = page.get("revisions") or []
        if not revisions:
            return None

        revision = revisions[0]
        revised_at = _parse_timestamp(revision.get("timestamp"))
        revision_id = revision.get("revid")
        page_title = page.get("title")
        if revised_at is None or revision_id is None or not page_title:
            return None

        return RevisionMetadata(
            revision_id=str(revision_id),
            revised_at=revised_at,
            title=str(page_title),
            is_redirect=is_redirect,
        )

    async def _query(self, url: str, host: str, params: dict) -> dict | None:
        """429면 물러섰다가 다시 묻는다. **끝내 안 되면 `None`이지 예외가 아니다.**"""
        backoff = _INITIAL_BACKOFF_SECONDS
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                async with httpx.AsyncClient(
                    timeout=_TIMEOUT_SECONDS,
                    follow_redirects=True,
                    transport=self._transport,
                ) as client:
                    response = await client.get(
                        _API.format(host=host),
                        params=params,
                        headers={"User-Agent": _USER_AGENT},
                    )
                if response.status_code == 429:
                    if attempt == _MAX_ATTEMPTS:
                        logger.warning(
                            "[ontology.revision] 429 — %d회 시도 후 포기 | url=%s",
                            attempt,
                            url,
                        )
                        return None
                    wait = min(
                        _retry_after_seconds(response) or backoff,
                        _MAX_BACKOFF_SECONDS,
                    )
                    logger.info(
                        "[ontology.revision] 429 — %.1fs 뒤 재시도 (%d/%d) | url=%s",
                        wait,
                        attempt,
                        _MAX_ATTEMPTS,
                        url,
                    )
                    await self._sleep(wait)
                    backoff = min(backoff * 2, _MAX_BACKOFF_SECONDS)
                    continue
                if response.status_code != 200:
                    logger.info(
                        "[ontology.revision] API 본문 아님 | url=%s | status=%s",
                        url,
                        response.status_code,
                    )
                    return None
                return response.json()
            except (httpx.HTTPError, ValueError) as exc:
                # **수집을 멈추지 않는다.** 계보만 비고 본문은 그대로 저장된다.
                logger.warning(
                    "[ontology.revision] 계보 조회 실패 | url=%s | %s", url, exc
                )
                return None
        return None
