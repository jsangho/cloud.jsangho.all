from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException
from ontology.adapter.inbound.api.schemas.crawl_scrape_pipeline_schema import (
    CrawlScrapePipelineRequest,
    CrawlScrapePipelineResponse,
)
from ontology.adapter.inbound.api.schemas.crawler_schema import CrawlResultResponse
from ontology.adapter.inbound.api.schemas.scraper_schema import ScrapeResultResponse
from ontology.app.ports.input.crawler_use_case import CrawlerUseCase
from ontology.app.ports.input.scraper_use_case import ScraperUseCase
from ontology.dependencies.crawler_provider import get_crawler_use_case
from ontology.dependencies.scraper_provider import get_scraper_use_case

logger = logging.getLogger("uvicorn.error")

crawl_scrape_pipeline_router = APIRouter(
    prefix="/crawl-scrape-pipeline", tags=["crawl-scrape-pipeline"]
)


@crawl_scrape_pipeline_router.post("/run", response_model=CrawlScrapePipelineResponse)
async def run(
    schema: Annotated[CrawlScrapePipelineRequest | None, Body()] = None,
    crawler_use_case: CrawlerUseCase = Depends(get_crawler_use_case),
    scraper_use_case: ScraperUseCase = Depends(get_scraper_use_case),
) -> CrawlScrapePipelineResponse:
    logger.info("[ontology/crawl-scrape-pipeline/run] 파이프라인 시작")
    website = schema.website.strip() if schema and schema.website else None
    keyword = schema.keyword.strip() if schema and schema.keyword else None
    crawl_result = await crawler_use_case.crawl(website=website, keyword=keyword)
    if crawl_result is None:
        raise HTTPException(
            status_code=404, detail="레디스에 대기 중인 크롤링 작업이 없습니다."
        )

    scrape_result = await scraper_use_case.scrape(crawl_result)
    logger.info(
        "[ontology/crawl-scrape-pipeline/run] 파이프라인 완료 | website=%s | keyword_found=%s",
        crawl_result.website,
        scrape_result.keyword_found,
    )
    return CrawlScrapePipelineResponse(
        crawl=CrawlResultResponse(
            website=crawl_result.website,
            keyword=crawl_result.keyword,
            status_code=crawl_result.status_code,
            fetched_at=crawl_result.fetched_at,
            content_length=crawl_result.content_length,
            saved_path=crawl_result.saved_path,
        ),
        scrape=ScrapeResultResponse(
            website=scrape_result.website,
            keyword=scrape_result.keyword,
            title=scrape_result.title,
            meta_description=scrape_result.meta_description,
            body_text=scrape_result.body_text,
            keyword_found=scrape_result.keyword_found,
            scraped_at=scrape_result.scraped_at,
            saved_path=scrape_result.saved_path,
        ),
    )
