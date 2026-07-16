from __future__ import annotations

import logging
from datetime import UTC, datetime

import httpx

from ontology.app.dtos.crawler_dto import FetchedPage
from ontology.app.ports.output.web_page_fetcher_port import WebPageFetcherPort

logger = logging.getLogger("uvicorn.error")

_USER_AGENT = "jsangho-ontology-crawler/1.0"
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
        )
