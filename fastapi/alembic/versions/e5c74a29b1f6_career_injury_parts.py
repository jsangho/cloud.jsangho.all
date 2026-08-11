"""부상 부위와 그 이력

Revision ID: e5c74a29b1f6
Revises: d1b6f83a95c7
Create Date: 2026-08-11

무릎과 목은 같은 부상이 아니다
(`apps/wwe_game/_docs/career-simulator-harness.md` §3-D43).

- `condition_part` — 지금 다친 곳. 건강하면 None
- `injured_parts` — **지금까지 다친 적 있는 부위 전부**

두 번째가 이 개정의 핵심이다. 부위가 회복 주차만 바꾸면 숫자에 이름표를 붙인 것에
지나지 않는다 — **몸이 기억해야** 커리어 후반이 앞부분과 달라진다. 한 번 무너진
무릎은 다음에도 무릎이고(재발 확률 55%), 두 번째는 더 오래 간다(회복 ×1.3).

`injured_parts`가 JSON인 이유는 `flags`·`titles_held`와 같다 — 진행 한 번이 세이브를
통째로 다시 쓰므로(§3-D6) 조회 단위가 아닌 목록을 표로 빼면 저장마다 행을 지웠다
다시 넣게 된다.

**옛 세이브는 부위 없이 읽힌다** — 이력이 비어 있으니 첫 부상부터 새로 쌓기 시작한다.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e5c74a29b1f6"
down_revision: str | Sequence[str] | None = "d1b6f83a95c7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "career_runs", sa.Column("condition_part", sa.String(20), nullable=True)
    )
    op.add_column(
        "career_runs",
        sa.Column(
            "injured_parts", sa.JSON(), nullable=False, server_default=sa.text("'[]'")
        ),
    )


def downgrade() -> None:
    op.drop_column("career_runs", "injured_parts")
    op.drop_column("career_runs", "condition_part")
