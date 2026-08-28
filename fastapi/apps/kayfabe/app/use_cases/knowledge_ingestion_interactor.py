"""지식 적재 유스케이스 — 하네스 §10-T3.

수집(허브) → 쪼개기(도메인) → 임베딩 → 저장의 순서를 엮는다. HTTP도 pgvector도
모른다 — 전부 포트 뒤에 있다.

**한 문서의 실패가 나머지를 멈추지 않는다.** 20개 중 3개가 robots.txt에 막혔다고
나머지 17개를 버리면, 재실행이 그 17개를 또 받아 오게 된다.
"""

from __future__ import annotations

import logging
from urllib.parse import urlparse

from kayfabe.app.dtos.knowledge_ingestion_dto import (
    IngestionSummary,
    IngestKnowledgeCommand,
    NewKnowledgeChunk,
    SourceDocument,
)
from kayfabe.app.ports.input.knowledge_ingestion_use_case import (
    KnowledgeIngestionUseCase,
)
from kayfabe.app.ports.output.knowledge_chunk_repository import KnowledgeChunkRepository
from kayfabe.app.ports.output.public_source_port import (
    PublicSourcePort,
    SourceNotAllowedError,
)
from kayfabe.app.ports.output.text_embedding_port import (
    EmbeddingUnavailableError,
    TextEmbeddingPort,
)
from kayfabe.domain.services.knowledge_chunking import (
    chunk_document,
    content_fingerprint,
)

logger = logging.getLogger("uvicorn.error")


class KnowledgeIngestionInteractor(KnowledgeIngestionUseCase):
    def __init__(
        self,
        source: PublicSourcePort,
        embedder: TextEmbeddingPort,
        repository: KnowledgeChunkRepository,
        *,
        max_chunks_per_document: int | None = None,
    ) -> None:
        self._source = source
        self._embedder = embedder
        self._repository = repository
        #: 문서당 청크 상한. 위키 인물 문서는 대부분이 타이틀 이력과 각주라,
        #: 앞부분만 담아도 근거로는 충분하고 임베딩 시간이 크게 줄어든다.
        self._max_chunks = max_chunks_per_document

    async def ingest(self, command: IngestKnowledgeCommand) -> IngestionSummary:
        collected = 0
        total_chunks = 0
        stored = 0
        failed = 0
        provenance_unavailable = 0

        for url in command.urls:
            document = await self._collect(url)
            if document is None:
                continue
            collected += 1
            if document.revised_at is None:
                # 본문은 받았지만 개정본 시각을 모른다 — 수집 실패가 아니다.
                # 이 문서를 인용한 예측은 시간 게이트를 통과할 수 없다는 뜻이라
                # 요약에 남겨 두고, 여기서 멈추지는 않는다.
                provenance_unavailable += 1
                logger.info(
                    "[kayfabe.knowledge_ingestion] 개정본 계보 없음 | url=%s", url
                )

            prepared, failures = await self._prepare(document)
            total_chunks += len(prepared) + failures
            failed += failures
            if prepared:
                stored += await self._repository.replace_document_chunks(prepared)

        duplicates = total_chunks - failed - stored
        logger.info(
            "[kayfabe.knowledge_ingestion] 적재 완료 | 요청=%d 수집=%d 청크=%d "
            "저장=%d 중복=%d 실패=%d 계보없음=%d",
            len(command.urls),
            collected,
            total_chunks,
            stored,
            duplicates,
            failed,
            provenance_unavailable,
        )
        return IngestionSummary(
            requested=len(command.urls),
            collected=collected,
            chunks=total_chunks,
            stored=stored,
            duplicates=duplicates,
            failed=failed,
            provenance_unavailable=provenance_unavailable,
        )

    async def _collect(self, url: str) -> SourceDocument | None:
        """허용 목록 밖 주소는 **여기서 멈추지 않고 기록만 남긴다.**

        여러 URL을 한 번에 넣는 경로라, 오타 하나가 나머지 수집을 통째로 취소하면
        재실행 비용이 상대 서버로 간다. 대신 경고로 남겨 목록을 고칠 수 있게 한다.
        """
        try:
            return await self._source.collect(url)
        except SourceNotAllowedError as exc:
            logger.warning("[kayfabe.knowledge_ingestion] 허용 목록 밖 | %s", exc)
            return None

    async def _prepare(
        self, document: SourceDocument
    ) -> tuple[list[NewKnowledgeChunk], int]:
        domain = _domain_of(document.url)
        prepared: list[NewKnowledgeChunk] = []
        failed = 0

        contents = chunk_document(document.text)
        if self._max_chunks is not None:
            contents = contents[: self._max_chunks]

        for content in contents:
            try:
                embedding = await self._embedder.embed(content)
            except EmbeddingUnavailableError as exc:
                # 벡터 없는 청크는 검색에 잡히지 않는다. 저장해 봐야 죽은 행이다.
                logger.warning(
                    "[kayfabe.knowledge_ingestion] 임베딩 실패 | url=%s | %s",
                    document.url,
                    exc,
                )
                failed += 1
                continue

            prepared.append(
                NewKnowledgeChunk(
                    source_url=document.url,
                    source_domain=domain,
                    title=document.title,
                    content=content,
                    content_hash=content_fingerprint(content),
                    embedding=embedding,
                    published_at=document.published_at,
                    source_revision_id=document.revision_id,
                    source_revised_at=document.revised_at,
                )
            )
        return prepared, failed


def _domain_of(url: str) -> str:
    return (urlparse(url).hostname or "").lower()
