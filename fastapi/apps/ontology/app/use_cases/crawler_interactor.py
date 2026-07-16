from __future__ import annotations

import logging

from ontology.app.dtos.crawler_dto import CrawlJob, CrawlResult
from ontology.app.ports.input.crawler_use_case import CrawlerUseCase
from ontology.app.ports.output.crawl_job_queue_port import CrawlJobQueuePort
from ontology.app.ports.output.crawl_result_repository import CrawlResultRepository
from ontology.app.ports.output.web_page_fetcher_port import WebPageFetcherPort

logger = logging.getLogger("uvicorn.error")


class CrawlerInteractor(CrawlerUseCase):
    def __init__(
        self,
        queue: CrawlJobQueuePort,
        fetcher: WebPageFetcherPort,
        repository: CrawlResultRepository,
    ) -> None:
        self._queue = queue
        self._fetcher = fetcher
        self._repository = repository

    async def crawl(
        self, website: str | None = None, keyword: str | None = None
    ) -> CrawlResult | None:
        if website:
            job = CrawlJob(website=website, keyword=keyword or "")
        else:
            job = await self._queue.pop_next_job()
            if job is None:
                logger.info("[ontology.crawler] 대기 중인 크롤링 작업 없음")
                return None

        logger.info(
            "[ontology.crawler] 크롤링 시작 | website=%s | keyword=%s",
            job.website,
            job.keyword,
        )
        page = await self._fetcher.fetch(job.website)
        result = await self._repository.save(
            website=job.website,
            keyword=job.keyword,
            status_code=page.status_code,
            html=page.html,
            fetched_at=page.fetched_at,
        )
        logger.info(
            "[ontology.crawler] 크롤링 완료 | website=%s | status=%s | saved_path=%s",
            job.website,
            page.status_code,
            result.saved_path,
        )
        return result
