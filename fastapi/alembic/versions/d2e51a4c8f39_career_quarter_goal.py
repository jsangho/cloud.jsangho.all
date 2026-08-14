"""career_runs에 분기 목표 두 칸 (하네스 §3-D80)

**옛 세이브는 `NULL`·`-1`로 남는다** — 이어 갈 때 그 분기의 목표를 처음 묻는다.
목표를 고른 적 없는 커리어와 "그냥 뛴다"를 고른 커리어를 구별해야 해서
`goal`은 nullable이다.

Revision ID: d2e51a4c8f39
Revises: a7f31c9d0b48
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d2e51a4c8f39"
down_revision: str | Sequence[str] | None = "a7f31c9d0b48"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("career_runs", sa.Column("goal", sa.String(16), nullable=True))
    op.add_column(
        "career_runs",
        sa.Column("goal_quarter", sa.Integer(), nullable=False, server_default="-1"),
    )


def downgrade() -> None:
    op.drop_column("career_runs", "goal_quarter")
    op.drop_column("career_runs", "goal")
