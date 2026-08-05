"""예측 근거 지식 청크 테이블 추가

Revision ID: d1c7f3b80204
Revises: c5a2e91d7b34
Create Date: 2026-08-05

`apps/kayfabe/_docs/ai-match-predictions-harness.md` §6의 세 번째 테이블이다.
서사·루머 에이전트가 근거로 읽을 공개 소스 조각을 담는다.

`vector` 확장은 이미 설치돼 있다(`wrestlers.embedding`이 운영에서 쓰고 있다).
그래서 여기서 `CREATE EXTENSION`을 다시 하지 않는다.

**인덱스(ivfflat/hnsw)를 만들지 않는다.** 행이 수천 건 규모라 순차 스캔이 더 빠르고,
ivfflat은 데이터가 적재된 뒤 만들어야 리스트가 제대로 잡힌다. 적재 규모가 커지면
그때 별도 마이그레이션으로 추가한다.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op
from core.matrix.vault_keymaker_secret_manager import EMBEDDING_DIM

revision: str = "d1c7f3b80204"
down_revision: str | Sequence[str] | None = "c5a2e91d7b34"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ple_knowledge_chunks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        # 출처 없는 지식은 근거로 쓰지 않는다(하네스 §3-D6) — DB에서 막는다.
        sa.Column("source_url", sa.String(length=500), nullable=False),
        sa.Column("source_domain", sa.String(length=120), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        # 같은 글을 다시 수집해도 한 벌만 남는다.
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=True),
        sa.Column(
            "collected_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("content_hash", name="uq_knowledge_chunk_content"),
    )
    op.create_index(
        op.f("ix_ple_knowledge_chunks_source_domain"),
        "ple_knowledge_chunks",
        ["source_domain"],
    )
    op.create_index(
        op.f("ix_ple_knowledge_chunks_published_at"),
        "ple_knowledge_chunks",
        ["published_at"],
    )


def downgrade() -> None:
    """수집한 지식이 사라진다. 재수집은 외부 사이트에 다시 요청을 보내는 작업이다."""
    op.drop_index(
        op.f("ix_ple_knowledge_chunks_published_at"), table_name="ple_knowledge_chunks"
    )
    op.drop_index(
        op.f("ix_ple_knowledge_chunks_source_domain"), table_name="ple_knowledge_chunks"
    )
    op.drop_table("ple_knowledge_chunks")
