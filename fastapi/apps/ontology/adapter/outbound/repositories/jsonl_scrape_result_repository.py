from __future__ import annotations

import asyncio
import json
from pathlib import Path

from ontology.app.dtos.scraper_dto import ScrapeResult
from ontology.app.ports.output.scrape_result_repository import ScrapeResultRepository

_DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[3] / "resources" / "scraped"


class JsonlScrapeResultRepository(ScrapeResultRepository):
    """구조화 스크래핑 결과를 날짜별 JSONL 파일(resources/scraped/{yyyy-mm-dd}.jsonl)에 적재하는 어댑터."""

    def __init__(self, output_dir: str | Path = _DEFAULT_OUTPUT_DIR) -> None:
        self._output_dir = Path(output_dir)

    async def save(
        self,
        website: str,
        keyword: str,
        title: str | None,
        meta_description: str | None,
        body_text: str,
        keyword_found: bool,
        scraped_at: str,
    ) -> ScrapeResult:
        return await asyncio.to_thread(
            self._write,
            website,
            keyword,
            title,
            meta_description,
            body_text,
            keyword_found,
            scraped_at,
        )

    def _write(
        self,
        website: str,
        keyword: str,
        title: str | None,
        meta_description: str | None,
        body_text: str,
        keyword_found: bool,
        scraped_at: str,
    ) -> ScrapeResult:
        self._output_dir.mkdir(parents=True, exist_ok=True)
        file_path = self._output_dir / f"{scraped_at[:10]}.jsonl"
        record = {
            "website": website,
            "keyword": keyword,
            "title": title,
            "meta_description": meta_description,
            "body_text": body_text,
            "keyword_found": keyword_found,
            "scraped_at": scraped_at,
        }
        with file_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

        return ScrapeResult(
            website=website,
            keyword=keyword,
            title=title,
            meta_description=meta_description,
            body_text=body_text,
            keyword_found=keyword_found,
            scraped_at=scraped_at,
            saved_path=str(file_path),
        )
