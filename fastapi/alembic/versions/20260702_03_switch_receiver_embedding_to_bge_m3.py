"""switch receiver_emails.embedding to bge-m3 (1024-dim)

Revision ID: 20260702_03
Revises: 20260702_02
Create Date: 2026-07-02

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260702_03"
down_revision: str | None = "20260702_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 기존 임베딩(Gemini, 3072차원)은 새 모델(bge-m3, 1024차원)과 호환되지 않아 재생성이 필요하다.
    op.execute("TRUNCATE TABLE receiver_emails")
    op.execute("ALTER TABLE receiver_emails ALTER COLUMN embedding TYPE vector(1024)")


def downgrade() -> None:
    op.execute("TRUNCATE TABLE receiver_emails")
    op.execute("ALTER TABLE receiver_emails ALTER COLUMN embedding TYPE vector(3072)")
