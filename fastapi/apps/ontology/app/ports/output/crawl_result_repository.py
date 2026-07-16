from __future__ import annotations

from abc import ABC, abstractmethod

from ontology.app.dtos.crawler_dto import CrawlResult


class CrawlResultRepository(ABC):
    """크롤링 원본 결과를 영속화하는 출력 포트."""

    @abstractmethod
    async def save(
        self,
        website: str,
        keyword: str,
        status_code: int,
        html: str,
        fetched_at: str,
    ) -> CrawlResult: ...
