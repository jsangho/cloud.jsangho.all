"""widen wrestlers.height/weight further (citation-footnote contamination in CSV)

Revision ID: 20260714_06
Revises: 20260714_05
Create Date: 2026-07-14

가정 사항:
- CSV 적재 중 일부 행(예: Jacy Jayne, Anthony Luke)의 height/weight 값에
  Wikipedia 각주 텍스트가 섞여 들어와 20260714_05에서 넓힌 한도(50/30자)도
  초과했다 (최대 145자 관측). 데이터 정제 대신 컬럼을 여유 있게 넓힌다.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260714_06"
down_revision: str | None = "20260714_05"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "wrestlers", "height", type_=sa.String(length=255), existing_type=sa.String(50)
    )
    op.alter_column(
        "wrestlers", "weight", type_=sa.String(length=255), existing_type=sa.String(30)
    )


def downgrade() -> None:
    op.alter_column(
        "wrestlers", "height", type_=sa.String(length=50), existing_type=sa.String(255)
    )
    op.alter_column(
        "wrestlers", "weight", type_=sa.String(length=30), existing_type=sa.String(255)
    )
