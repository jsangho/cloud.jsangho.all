"""커리어 세이브에 도전권과 가방 두 칸

Revision ID: b8f4d1c62073
Revises: a7e3c5b91048
Create Date: 2026-08-11

럼블·챔버 우승이 주는 **레슬매니아 1선 도전권**과 머니 인 더 뱅크 **가방**
(`apps/wwe_game/_docs/career-simulator-harness.md` §3-D36).

- `title_shot` — 그해 레슬매니아에서 쓰고 사라진다
- `briefcase_week` — 가방을 딴 주차. 0이면 없다

**가방이 불리언이 아닌 이유는 기한이다.** 1년 안에 안 쓰면 규칙이 대신 쓴다
(2026-08-11 사용자 확인). 언제 땄는지를 모르면 그 기한을 잴 수 없다.

`run.flags`가 아니라 표의 칸인 이유: 표식은 **카드가 남기고 규칙이 읽는** 값이라는
약속이 있고(§3-D26), 이 둘은 반대로 **규칙이 주고 카드가 읽는다.**

**옛 세이브는 기본값으로 읽힌다** — 도전권 없음, 가방 없음. 진행에 지장이 없다.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b8f4d1c62073"
down_revision: str | Sequence[str] | None = "a7e3c5b91048"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "career_runs",
        sa.Column(
            "title_shot", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.add_column(
        "career_runs",
        sa.Column("briefcase_week", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("career_runs", "briefcase_week")
    op.drop_column("career_runs", "title_shot")
