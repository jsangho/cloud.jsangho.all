"""add embedding column to stadium/team/schedule/player (RAG search)

Revision ID: 20260714_03
Revises: 20260714_02
Create Date: 2026-07-14

가정 사항:
- soccer-database.md 3번 섹션 5는 원래 "임의로 vector 컬럼을 추가하지 말 것"이라
  명시했으나, 이번엔 사용자가 명시적으로 4개 테이블 모두에 embedding 추가를
  요청하여 예외로 적용한다.
- 차원은 이 프로젝트의 표준 core.matrix.vault_keymaker_secret_manager.EMBEDDING_DIM
  (1024, bge-m3)을 따른다 (wrestlers/receiver_emails와 동일 컨벤션).
- pgvector extension은 20260702_02 마이그레이션에서 이미 보장되어 있어 별도로
  추가하지 않는다.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op

revision: str = "20260714_03"
down_revision: str | None = "20260714_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EMBEDDING_DIM = 1024


def upgrade() -> None:
    for table in ("stadium", "team", "schedule", "player"):
        op.add_column(
            table, sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=True)
        )


def downgrade() -> None:
    for table in ("stadium", "team", "schedule", "player"):
        op.drop_column(table, "embedding")
