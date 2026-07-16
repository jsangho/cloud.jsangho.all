from __future__ import annotations

from abc import ABC, abstractmethod

from ontology.app.dtos.crawler_dto import CrawlResult


class CrawlerUseCase(ABC):
    """웹사이트·키워드를 받아 단일 페이지를 크롤링하는 입력 포트.

    website를 직접 주면 그 자리에서 크롤링하고, 안 주면 레디스 작업 큐에서
    다음 작업을 꺼내 크롤링한다.
    """

    @abstractmethod
    async def crawl(
        self, website: str | None = None, keyword: str | None = None
    ) -> CrawlResult | None: ...
