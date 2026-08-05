from __future__ import annotations

from abc import ABC, abstractmethod

from kayfabe.app.dtos.knowledge_ingestion_dto import (
    IngestionSummary,
    IngestKnowledgeCommand,
)


class KnowledgeIngestionUseCase(ABC):
    @abstractmethod
    async def ingest(self, command: IngestKnowledgeCommand) -> IngestionSummary:
        """공개 소스를 모아 `ple_knowledge_chunks`에 넣는다.

        **조회 경로와 분리돼 있다** — 사용자 페이지 진입이 외부 사이트에 요청을 보내는
        일은 없어야 한다(하네스 §2-D7).
        """
