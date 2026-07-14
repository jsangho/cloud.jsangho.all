"""change soccer stadium/team/schedule/player embedding dim to 1024 (bge-m3)

Revision ID: 20260714_02
Revises: 20260714_01
Create Date: 2026-07-14

가정 사항:
- 프로젝트에 이미 구축된 임베딩 생성기(core.matrix.vault_keymaker_secret_manager.Keymaker,
  Ollama bge-m3, 1024차원)를 재사용하기로 했다. 20260714_01에서 OpenAI
  text-embedding-3-small 기준 1536차원으로 만들었던 것을 1024차원으로 변경한다.
- 4개 테이블 모두 embedding 값이 아직 전부 NULL이라 TRUNCATE 없이 컬럼 타입만 변경한다.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260714_02"
down_revision: str | None = "20260714_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = ("stadium", "team", "schedule", "player")


def upgrade() -> None:
    for table in _TABLES:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN embedding TYPE vector(1024)")


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.execute(f"ALTER TABLE {table} ALTER COLUMN embedding TYPE vector(1536)")
