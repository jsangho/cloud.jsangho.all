"""지식 청크 저장 어댑터 (Neon PostgreSQL + pgvector).

**재실행이 안전해야 한다.** 같은 URL을 주기적으로 다시 수집하는 것이 정상 운용이므로,
중복은 오류가 아니라 기본 동작이다. `content_hash` 유니크 제약 위에서
`ON CONFLICT DO NOTHING`으로 처리한다 — 먼저 조회해서 거르면 그 사이에 들어온 행과
경합한다.
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from kayfabe.adapter.outbound.orm.knowledge_chunk_orm import KnowledgeChunkModel
from kayfabe.app.dtos.knowledge_ingestion_dto import NewKnowledgeChunk
from kayfabe.app.ports.output.knowledge_chunk_repository import KnowledgeChunkRepository


class KnowledgeChunkPgRepository(KnowledgeChunkRepository):
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def save_new(self, chunks: Sequence[NewKnowledgeChunk]) -> int:
        rows = _deduplicated(chunks)
        if not rows:
            return 0

        stmt = (
            insert(KnowledgeChunkModel)
            .values(rows)
            .on_conflict_do_nothing(index_elements=["content_hash"])
            .returning(KnowledgeChunkModel.id)
        )
        inserted = (await self.db.execute(stmt)).scalars().all()
        await self.db.flush()
        return len(inserted)


def _deduplicated(chunks: Sequence[NewKnowledgeChunk]) -> list[dict[str, object]]:
    """한 번의 INSERT 안에 같은 해시가 두 번 들어가지 않게 한다.

    같은 문서에서 똑같은 문단이 두 번 뽑히는 일이 실제로 있다(반복되는 안내 문구).
    DB도 걸러 주지만, 넣는 쪽이 세는 숫자와 실제 저장 수가 어긋나면 요약이 거짓말이 된다.
    """
    seen: set[str] = set()
    rows: list[dict[str, object]] = []
    for chunk in chunks:
        if chunk.content_hash in seen:
            continue
        seen.add(chunk.content_hash)
        rows.append(
            {
                "source_url": chunk.source_url,
                "source_domain": chunk.source_domain,
                "title": chunk.title,
                "content": chunk.content,
                "content_hash": chunk.content_hash,
                "embedding": chunk.embedding,
                "published_at": chunk.published_at,
            }
        )
    return rows
