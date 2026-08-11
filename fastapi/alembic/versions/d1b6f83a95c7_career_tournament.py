"""커리어 세이브에 토너먼트 진출 라운드

Revision ID: d1b6f83a95c7
Revises: c9a2e57b3184
Create Date: 2026-08-11

킹 앤 퀸 오브 더 링 (`apps/wwe_game/_docs/career-simulator-harness.md` §3-D33).

**한 주에 안 끝나는 유일한 형식이라 상태가 필요하다.** 다른 경기는 그 주에 결판이
나므로 리포트 하나로 끝나지만, 토너먼트는 "지난주에 이겼는가"를 다음 주가 알아야 한다.

대회가 지나가면 0으로 돌아간다 — 해마다 새 대진표가 열린다.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d1b6f83a95c7"
down_revision: str | Sequence[str] | None = "c9a2e57b3184"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "career_runs",
        sa.Column(
            "tournament_round", sa.Integer(), nullable=False, server_default="0"
        ),
    )


def downgrade() -> None:
    op.drop_column("career_runs", "tournament_round")
