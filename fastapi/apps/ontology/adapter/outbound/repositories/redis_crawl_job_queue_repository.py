from __future__ import annotations

import json
import logging
import os

import redis.asyncio as redis

from ontology.app.dtos.crawler_dto import CrawlJob
from ontology.app.ports.output.crawl_job_queue_port import CrawlJobQueuePort

logger = logging.getLogger("uvicorn.error")

_REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
_REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))
_QUEUE_KEY = os.environ.get("ONTOLOGY_CRAWL_QUEUE_KEY", "ontology:crawl:jobs")


class RedisCrawlJobQueueRepository(CrawlJobQueuePort):
    """레디스 리스트(기본 키: ontology:crawl:jobs)에서 {"website", "keyword"} JSON 작업을 꺼내오는 어댑터."""

    def __init__(self, host: str | None = None, port: int | None = None) -> None:
        self._client = redis.Redis(
            host=host or _REDIS_HOST,
            port=port or _REDIS_PORT,
            decode_responses=True,
        )

    async def pop_next_job(self) -> CrawlJob | None:
        raw = await self._client.rpop(_QUEUE_KEY)
        if raw is None:
            return None

        try:
            payload = json.loads(raw)
            return CrawlJob(website=payload["website"], keyword=payload["keyword"])
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            logger.warning(
                "[ontology.redis_crawl_job_queue_repository] 잘못된 작업 payload, 건너뜀 | raw=%r | error=%s",
                raw,
                exc,
            )
            return None
