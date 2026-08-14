"""career_runs에 재계약 협상 칸 (하네스 §3-D84)

**저장해야 하는 이유**: 협상은 답할 때까지 진행을 막으므로(§11-1), 이 칸이 안
남으면 새로고침 한 번에 협상이 사라지고 계약 없이 뛰게 된다.

Revision ID: f4a72b9e31d0
Revises: d2e51a4c8f39
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f4a72b9e31d0"
down_revision: str | Sequence[str] | None = "d2e51a4c8f39"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "career_runs",
        sa.Column("offer_week", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("career_runs", "offer_week")
