from __future__ import annotations

import asyncio
import json
from pathlib import Path

from ontology.app.dtos.crawler_dto import CrawlResult
from ontology.app.ports.output.crawl_result_repository import CrawlResultRepository

_DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[3] / "resources" / "crawled"


class JsonlCrawlResultRepository(CrawlResultRepository):
    """크롤링 원본 결과를 날짜별 JSONL 파일(resources/crawled/{yyyy-mm-dd}.jsonl)에 적재하는 어댑터."""

    def __init__(self, output_dir: str | Path = _DEFAULT_OUTPUT_DIR) -> None:
        self._output_dir = Path(output_dir)

    async def save(
        self,
        website: str,
        keyword: str,
        status_code: int,
        html: str,
        fetched_at: str,
    ) -> CrawlResult:
        return await asyncio.to_thread(
            self._write, website, keyword, status_code, html, fetched_at
        )

    def _write(
        self,
        website: str,
        keyword: str,
        status_code: int,
        html: str,
        fetched_at: str,
    ) -> CrawlResult:
        content_length = len(html)
        self._output_dir.mkdir(parents=True, exist_ok=True)
        file_path = self._output_dir / f"{fetched_at[:10]}.jsonl"
        record = {
            "website": website,
            "keyword": keyword,
            "status_code": status_code,
            "html": html,
            "fetched_at": fetched_at,
            "content_length": content_length,
        }
        with file_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

        return CrawlResult(
            website=website,
            keyword=keyword,
            status_code=status_code,
            html=html,
            fetched_at=fetched_at,
            content_length=content_length,
            saved_path=str(file_path),
        )
