"""career_runs에 다시 묻는 주차 (하네스 §3-D88)

**쿨다운 하나로는 "평생 쓰기"를 표현할 수 없다.** 언제 다시 물을 것인가를 직접
담으면 분기·1년·평생이 전부 이 한 값이 된다.

옛 행은 0이고, 그때는 첫 분기 규칙을 쓴다 — 곧 옛 세이브의 동작이 그대로다.

Revision ID: c8d3a1f60b27
Revises: b7e2f9a35c81
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c8d3a1f60b27"
down_revision: str | Sequence[str] | None = "b7e2f9a35c81"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "career_runs",
        sa.Column(
            "finisher_ask_week", sa.Integer(), nullable=False, server_default="0"
        ),
    )


def downgrade() -> None:
    op.drop_column("career_runs", "finisher_ask_week")
