from __future__ import annotations

from ontology.adapter.outbound.httpx_web_page_fetcher import HttpxWebPageFetcher
from ontology.adapter.outbound.repositories.jsonl_crawl_result_repository import (
    JsonlCrawlResultRepository,
)
from ontology.adapter.outbound.repositories.redis_crawl_job_queue_repository import (
    RedisCrawlJobQueueRepository,
)
from ontology.app.ports.input.crawler_use_case import CrawlerUseCase
from ontology.app.use_cases.crawler_interactor import CrawlerInteractor


def get_crawler_use_case() -> CrawlerUseCase:
    return CrawlerInteractor(
        queue=RedisCrawlJobQueueRepository(),
        fetcher=HttpxWebPageFetcher(),
        repository=JsonlCrawlResultRepository(),
    )
