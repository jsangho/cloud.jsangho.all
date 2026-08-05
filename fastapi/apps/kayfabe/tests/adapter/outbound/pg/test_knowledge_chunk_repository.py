"""지식 청크 저장 어댑터 테스트 — 하네스 §10-T3.

SQLite로는 못 본다: `Vector` 컬럼도 `ON CONFLICT`도 PostgreSQL 것이다. 그래서
**PostgreSQL 방언으로 컴파일한 SQL**과 배치 내 중복 제거 로직만 검증한다.

지키려는 것: **재실행이 안전하다.** 같은 URL을 주기적으로 다시 수집하는 것이 정상
운용이므로, 중복 삽입이 오류로 터지면 운영이 멈춘다.

실행:

    cd fastapi
    PYTHONUTF8=1 PYTHONPATH=apps uv run pytest apps/kayfabe/tests -q
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy.dialects import postgresql

from kayfabe.adapter.outbound.pg.knowledge_chunk_pg_repository import (
    KnowledgeChunkPgRepository,
    _deduplicated,
)
from kayfabe.app.dtos.knowledge_ingestion_dto import NewKnowledgeChunk


def _chunk(content: str = "본문", content_hash: str = "a" * 64) -> NewKnowledgeChunk:
    return NewKnowledgeChunk(
        source_url="https://www.wwe.com/shows/summerslam",
        source_domain="www.wwe.com",
        title="SummerSlam",
        content=content,
        content_hash=content_hash,
        embedding=[0.1, 0.2],
        published_at=datetime(2026, 8, 1, tzinfo=UTC),
    )


class _FakeSession:
    def __init__(self, inserted_ids: list[int]) -> None:
        self._inserted_ids = inserted_ids
        self.statements: list[Any] = []
        self.flushed = False

    async def execute(self, statement: Any) -> Any:
        self.statements.append(statement)
        ids = self._inserted_ids

        class _Result:
            def scalars(self) -> Any:
                class _Scalars:
                    def all(self) -> list[int]:
                        return ids

                return _Scalars()

        return _Result()

    async def flush(self) -> None:
        self.flushed = True


def _repository(session: Any) -> KnowledgeChunkPgRepository:
    return KnowledgeChunkPgRepository(db=session)  # type: ignore[arg-type]


def test_same_hash_is_inserted_once() -> None:
    """같은 문서에서 똑같은 문단이 두 번 뽑히는 일이 실제로 있다."""
    rows = _deduplicated([_chunk(), _chunk(), _chunk(content_hash="b" * 64)])

    assert len(rows) == 2
    assert {row["content_hash"] for row in rows} == {"a" * 64, "b" * 64}


def test_row_carries_source_columns() -> None:
    """`source_url`이 비면 DB가 거부한다 — 여기서 빠뜨리지 않는지 본다."""
    row = _deduplicated([_chunk()])[0]

    assert row["source_url"] == "https://www.wwe.com/shows/summerslam"
    assert row["source_domain"] == "www.wwe.com"
    assert row["published_at"] == datetime(2026, 8, 1, tzinfo=UTC)


@pytest.mark.asyncio
async def test_empty_batch_touches_nothing() -> None:
    session = _FakeSession([])

    assert await _repository(session).save_new([]) == 0
    assert session.statements == []


@pytest.mark.asyncio
async def test_conflicting_rows_are_skipped_not_raised() -> None:
    session = _FakeSession([1])

    stored = await _repository(session).save_new(
        [_chunk(), _chunk("다른 본문", "b" * 64)]
    )

    # 두 건을 넣었지만 DB가 하나만 받았다 — 나머지는 이미 있던 내용이다.
    assert stored == 1
    sql = str(session.statements[0].compile(dialect=postgresql.dialect()))
    assert "ON CONFLICT (content_hash) DO NOTHING" in sql
    assert "RETURNING ple_knowledge_chunks.id" in sql
    assert session.flushed
