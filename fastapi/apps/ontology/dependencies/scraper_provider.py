from __future__ import annotations

from ontology.adapter.outbound.repositories.jsonl_scrape_result_repository import (
    JsonlScrapeResultRepository,
)
from ontology.app.ports.input.scraper_use_case import ScraperUseCase
from ontology.app.use_cases.scraper_interactor import ScraperInteractor


def get_scraper_use_case() -> ScraperUseCase:
    return ScraperInteractor(repository=JsonlScrapeResultRepository())
