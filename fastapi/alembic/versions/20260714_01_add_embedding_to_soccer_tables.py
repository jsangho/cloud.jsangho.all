"""add embedding column to soccer stadium/team/schedule/player tables

Revision ID: 20260714_01
Revises: 20260713_02
Create Date: 2026-07-14

가정 사항:
- RAG 검색을 위한 embedding 컬럼(VECTOR(1536), OpenAI text-embedding-3-small 기준
  차원)을 stadium/team/schedule/player 4개 테이블 모두에 NULL 허용으로 추가한다.
  값을 채우는 배치/파이프라인은 이번 마이그레이션 범위에 포함하지 않는다.
- pgvector extension은 20260702_02 마이그레이션에서 이미 생성되어 있어
  별도로 추가하지 않는다.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "20260714_01"
down_revision: str | None = "20260713_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EMBEDDING_DIM = 1536

_TABLES = ("stadium", "team", "schedule", "player")


def upgrade() -> None:
    for table in _TABLES:
        op.add_column(
            table, sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=True)
        )


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.drop_column(table, "embedding")
