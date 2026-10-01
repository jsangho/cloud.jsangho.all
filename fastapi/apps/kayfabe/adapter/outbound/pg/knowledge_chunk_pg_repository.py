"""지식 청크 저장 어댑터 (Neon PostgreSQL + pgvector).

**재실행이 안전해야 한다.** 같은 URL을 주기적으로 다시 수집하는 것이 정상 운용이다.
그래서 두 가지를 한다.

1. **같은 `source_url`의 옛 청크를 지우고 새로 넣는다.** 위키 문서가 갱신되면
   `content_hash`가 달라져 그냥 넣을 경우 옛 판본이 계속 검색된다(하네스 §13-Q6).
2. 문서 사이에 겹치는 문단은 `content_hash` 유니크 제약 위에서
   `ON CONFLICT DO NOTHING`으로 흘려보낸다 — 먼저 조회해서 거르면 그 사이에
   들어온 행과 경합한다.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from kayfabe.adapter.outbound.orm.knowledge_chunk_orm import KnowledgeChunkModel
from kayfabe.app.dtos.knowledge_ingestion_dto import NewKnowledgeChunk
from kayfabe.app.ports.output.knowledge_chunk_repository import KnowledgeChunkRepository


class KnowledgeChunkPgRepository(KnowledgeChunkRepository):
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def replace_document_chunks(self, chunks: Sequence[NewKnowledgeChunk]) -> int:
        rows = _deduplicated(chunks)
        if not rows:
            return 0

        # 새 판본을 넣기 전에 그 문서의 옛 판본을 걷어낸다. 삭제와 삽입이 같은
        # 트랜잭션이라, 중간에 실패하면 옛 청크가 그대로 남는다.
        await self.db.execute(
            delete(KnowledgeChunkModel).where(
                KnowledgeChunkModel.source_url.in_({row["source_url"] for row in rows})
            )
        )

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
    # **`collected_at`을 DB 기본값에 맡기지 않는다.** `func.now()`는 문장 시각이
    # 아니라 트랜잭션 시작 시각이라, 한 번의 적재에 들어간 청크가 전부 같은 값을
    # 받는다. 그러면 배치 뒤쪽 문서는 `source_revised_at`이 `collected_at`보다
    # 미래가 되어 계보가 불완전으로 떨어진다 — 시간이 틀린 게 아니라 두 항이
    # 서로 다른 순간을 가리키던 것이다.
    #
    # 허브가 준 수집 시각이 정본이고, 없을 때만 **지금** 시각으로 메운다. 이 호출은
    # 문서 하나를 받아 임베딩까지 끝낸 뒤라 어떤 경우에도 수집보다 앞설 수 없다.
    fallback = datetime.now(UTC)
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
                "source_revision_id": chunk.source_revision_id,
                "source_revised_at": chunk.source_revised_at,
                "collected_at": chunk.collected_at or fallback,
            }
        )
    return rows
