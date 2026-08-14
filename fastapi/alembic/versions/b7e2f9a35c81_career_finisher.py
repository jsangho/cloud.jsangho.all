"""career_runs에 피니셔 두 칸 (하네스 §3-D88)

**빈 문자열이 곧 기본값이다** — 옛 행은 고른 적이 없고, 그때는 계열의 첫 기술을
쓴다. 고르지 않은 것과 못 고른 것을 나누지 않으므로 nullable로 두지 않는다.

Revision ID: b7e2f9a35c81
Revises: a91c4e7b2d05
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b7e2f9a35c81"
down_revision: str | Sequence[str] | None = "a91c4e7b2d05"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "career_runs",
        sa.Column("finisher", sa.String(length=30), nullable=False, server_default=""),
    )
    op.add_column(
        "career_runs",
        sa.Column(
            "finisher_name", sa.String(length=40), nullable=False, server_default=""
        ),
    )
    op.add_column(
        "career_runs",
        sa.Column("finisher_week", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("career_runs", "finisher_week")
    op.drop_column("career_runs", "finisher_name")
    op.drop_column("career_runs", "finisher")
