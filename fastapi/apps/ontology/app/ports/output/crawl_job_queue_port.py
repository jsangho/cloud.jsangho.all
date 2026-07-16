from __future__ import annotations

from abc import ABC, abstractmethod

from ontology.app.dtos.crawler_dto import CrawlJob


class CrawlJobQueuePort(ABC):
    """레디스 작업 큐에 크롤링할 웹사이트·키워드 작업을 넣고 꺼내는 출력 포트."""

    @abstractmethod
    async def push_job(self, job: CrawlJob) -> None: ...

    @abstractmethod
    async def pop_next_job(self) -> CrawlJob | None: ...
