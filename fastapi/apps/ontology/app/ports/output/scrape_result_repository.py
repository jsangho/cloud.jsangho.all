from __future__ import annotations

from abc import ABC, abstractmethod

from ontology.app.dtos.scraper_dto import ScrapeResult


class ScrapeResultRepository(ABC):
    """스크래핑으로 구조화 추출한 결과를 영속화하는 출력 포트."""

    @abstractmethod
    async def save(
        self,
        website: str,
        keyword: str,
        title: str | None,
        meta_description: str | None,
        body_text: str,
        keyword_found: bool,
        scraped_at: str,
    ) -> ScrapeResult: ...
