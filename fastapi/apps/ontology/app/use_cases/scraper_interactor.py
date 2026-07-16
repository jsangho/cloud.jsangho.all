from __future__ import annotations

import logging
import re
from datetime import UTC, datetime

from bs4 import BeautifulSoup

from ontology.app.dtos.crawler_dto import CrawlResult
from ontology.app.dtos.scraper_dto import ScrapeResult
from ontology.app.ports.input.scraper_use_case import ScraperUseCase
from ontology.app.ports.output.scrape_result_repository import ScrapeResultRepository

logger = logging.getLogger("uvicorn.error")

_WHITESPACE = re.compile(r"\s+")


class ScraperInteractor(ScraperUseCase):
    def __init__(self, repository: ScrapeResultRepository) -> None:
        self._repository = repository

    async def scrape(self, crawl_result: CrawlResult) -> ScrapeResult:
        logger.info(
            "[ontology.scraper] 스크래핑 시작 | website=%s | keyword=%s",
            crawl_result.website,
            crawl_result.keyword,
        )
        soup = BeautifulSoup(crawl_result.html, "html.parser")
        title = self._extract_title(soup)
        meta_description = self._extract_meta_description(soup)
        body_text = self._extract_body_text(soup)
        keyword_found = self._contains_keyword(crawl_result.keyword, title, body_text)

        result = await self._repository.save(
            website=crawl_result.website,
            keyword=crawl_result.keyword,
            title=title,
            meta_description=meta_description,
            body_text=body_text,
            keyword_found=keyword_found,
            scraped_at=datetime.now(UTC).isoformat(),
        )
        logger.info(
            "[ontology.scraper] 스크래핑 완료 | website=%s | keyword_found=%s | saved_path=%s",
            crawl_result.website,
            keyword_found,
            result.saved_path,
        )
        return result

    def _extract_title(self, soup: BeautifulSoup) -> str | None:
        if soup.title is None or soup.title.string is None:
            return None
        return soup.title.get_text(strip=True) or None

    def _extract_meta_description(self, soup: BeautifulSoup) -> str | None:
        tag = soup.find("meta", attrs={"name": "description"}) or soup.find(
            "meta", attrs={"property": "og:description"}
        )
        if tag is None:
            return None
        content = tag.get("content")
        return content.strip() if content else None

    def _extract_body_text(self, soup: BeautifulSoup) -> str:
        body = soup.body or soup
        text = body.get_text(separator=" ", strip=True)
        return _WHITESPACE.sub(" ", text).strip()

    def _contains_keyword(
        self, keyword: str, title: str | None, body_text: str
    ) -> bool:
        haystack = f"{title or ''} {body_text}".lower()
        return keyword.lower() in haystack
