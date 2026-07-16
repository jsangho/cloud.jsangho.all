from __future__ import annotations

from abc import ABC, abstractmethod

from ontology.app.dtos.crawler_dto import FetchedPage


class WebPageFetcherPort(ABC):
    """단일 URL을 HTTP GET으로 fetch하는 출력 포트."""

    @abstractmethod
    async def fetch(self, url: str) -> FetchedPage: ...
