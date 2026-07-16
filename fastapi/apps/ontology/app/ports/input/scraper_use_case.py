from __future__ import annotations

from abc import ABC, abstractmethod

from ontology.app.dtos.crawler_dto import CrawlResult
from ontology.app.dtos.scraper_dto import ScrapeResult


class ScraperUseCase(ABC):
    """크롤링 결과 HTML에서 제목·메타·본문을 구조화 추출하는 입력 포트."""

    @abstractmethod
    async def scrape(self, crawl_result: CrawlResult) -> ScrapeResult: ...
