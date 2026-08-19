"""career_runs에 산 시그니처 칸과 이름들 (하네스 §3-D92)

**이름은 돈으로 산다.** 칸을 사고(`signature_slots`) 그 칸에 이름을 새긴다
(`signature_names`) — 둘은 다른 구매다.

옛 행은 칸 0 · 빈 목록이고, **0은 기본 한 칸으로 읽는다** — 곧 동작이 변하지 않는다.

Revision ID: d3f5b81a29c4
Revises: c8d3a1f60b27
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d3f5b81a29c4"
down_revision: str | Sequence[str] | None = "c8d3a1f60b27"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "career_runs",
        sa.Column("signature_slots", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "career_runs",
        sa.Column(
            "signature_names",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
    )


def downgrade() -> None:
    op.drop_column("career_runs", "signature_names")
    op.drop_column("career_runs", "signature_slots")
