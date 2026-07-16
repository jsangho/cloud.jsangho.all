from pydantic import BaseModel

from ontology.adapter.inbound.api.schemas.crawler_schema import CrawlResultResponse
from ontology.adapter.inbound.api.schemas.scraper_schema import ScrapeResultResponse


class CrawlScrapePipelineRequest(BaseModel):
    website: str | None = None
    keyword: str | None = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "website": "https://example.com",
                "keyword": "이 페이지에서 가격 정보만 추출해줘",
            },
        }
    }


class CrawlScrapePipelineResponse(BaseModel):
    crawl: CrawlResultResponse
    scrape: ScrapeResultResponse
