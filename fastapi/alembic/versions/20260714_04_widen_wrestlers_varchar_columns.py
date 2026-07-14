"""widen wrestlers.height/weight/birth_date (CSV values exceed original VARCHAR limits)

Revision ID: 20260714_04
Revises: 20260714_03
Create Date: 2026-07-14

가정 사항 (wwe-roster-database.md 3번 섹션 가정 f):
- height VARCHAR(20)->VARCHAR(50): Hikuleo의 범위 표기
  ("6 ft 8 in (203 cm) - 6 ft 9 in (206 cm)", 40자)가 원래 제한을 초과했다.
- weight VARCHAR(20)->VARCHAR(30), birth_date VARCHAR(30)->VARCHAR(50): 각주 오염
  제거 후에도 여유를 두기 위해 함께 확장했다 (사용자 확인 완료).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260714_04"
down_revision: str | None = "20260714_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "wrestlers", "height", type_=sa.String(length=50), existing_type=sa.String(20)
    )
    op.alter_column(
        "wrestlers", "weight", type_=sa.String(length=30), existing_type=sa.String(20)
    )
    op.alter_column(
        "wrestlers",
        "birth_date",
        type_=sa.String(length=50),
        existing_type=sa.String(30),
    )


def downgrade() -> None:
    op.alter_column(
        "wrestlers", "height", type_=sa.String(length=20), existing_type=sa.String(50)
    )
    op.alter_column(
        "wrestlers", "weight", type_=sa.String(length=20), existing_type=sa.String(30)
    )
    op.alter_column(
        "wrestlers",
        "birth_date",
        type_=sa.String(length=30),
        existing_type=sa.String(50),
    )
