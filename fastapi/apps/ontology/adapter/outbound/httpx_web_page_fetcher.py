from __future__ import annotations

import logging
from datetime import UTC, datetime

import httpx

from ontology.app.dtos.crawler_dto import FetchedPage
from ontology.app.ports.output.web_page_fetcher_port import WebPageFetcherPort

logger = logging.getLogger("uvicorn.error")

# 위키미디어는 연락처 없는 봇 UA를 403으로 막는다(2026-11-11 실측 — httpx + 이 문자열만
# 보내면 "Please respect our robot policy"). 정책은 URL 또는 이메일 연락처를 요구한다.
_USER_AGENT = "jsangho-ontology-crawler/1.0 (https://jsangho.cloud)"
_TIMEOUT_SECONDS = 30.0


class HttpxWebPageFetcher(WebPageFetcherPort):
    """httpx로 단일 URL을 HTTP GET fetch하는 어댑터."""

    async def fetch(self, url: str) -> FetchedPage:
        async with httpx.AsyncClient(
            timeout=_TIMEOUT_SECONDS, follow_redirects=True
        ) as client:
            response = await client.get(url, headers={"User-Agent": _USER_AGENT})

        return FetchedPage(
            url=url,
            status_code=response.status_code,
            html=response.text,
            fetched_at=datetime.now(UTC).isoformat(),
            # 개정본 API가 없는 소스의 계보 재료다. 여기서 해석하지 않고 그대로 싣는다.
            etag=response.headers.get("etag"),
            last_modified=response.headers.get("last-modified"),
        )
