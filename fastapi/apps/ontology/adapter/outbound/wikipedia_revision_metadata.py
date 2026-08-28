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
"""

from __future__ import annotations

import logging
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


def _parse_timestamp(raw: object) -> datetime | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        parsed = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


class WikipediaRevisionMetadata(RevisionMetadataPort):
    """위키 문서 하나의 최신 개정본 계보를 읽는다.

    한 번에 한 문서만 묻는 이유는 부르는 쪽(`PublicSourceInteractor`)이 문서 단위로
    돌기 때문이다. 배치가 필요해지면 `revids=`/`titles=`에 `|`로 이어 붙이면 되는데,
    **`rvlimit`은 다중 문서와 함께 못 쓴다**(`invalidparammix`) — 그때는 `rvlimit`을
    빼야 한다.
    """

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
        }
        try:
            async with httpx.AsyncClient(
                timeout=_TIMEOUT_SECONDS, follow_redirects=True
            ) as client:
                response = await client.get(
                    _API.format(host=host),
                    params=params,
                    headers={"User-Agent": _USER_AGENT},
                )
            if response.status_code != 200:
                logger.info(
                    "[ontology.revision] API 본문 아님 | url=%s | status=%s",
                    url,
                    response.status_code,
                )
                return None
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            # **수집을 멈추지 않는다.** 계보만 비고 본문은 그대로 저장된다.
            logger.warning("[ontology.revision] 계보 조회 실패 | url=%s | %s", url, exc)
            return None

        pages = payload.get("query", {}).get("pages") or []
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
        )
