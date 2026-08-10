"""커리어 세이브에 소속 팀 한 칸

Revision ID: f4d0a8c1e762
Revises: e2b8c4f10593
Create Date: 2026-08-10

플레이어가 태그팀·스테이블에 합류하면 그 팀을 세이브가 들고 있어야 한다
(`apps/wwe_game/_docs/career-simulator-harness.md` §3-D30). 지금까지는 `flags`의
`in_tag_team`·`in_stable`로 **상태만** 알 수 있었고 누구와 무슨 이름인지는 없었다.

**표가 아니라 JSON 칼럼이다.** `titles_held`·`flags`와 같은 이유다 — 진행 한 번이
세이브를 통째로 다시 쓰므로(§3-D6) 조회 단위가 아닌 값을 표로 빼면 저장마다 행을
지웠다 다시 넣게 된다.

**nullable이다.** 혼자인 커리어가 정상이고, 이 마이그레이션 이전의 세이브도 전부
None으로 읽힌다.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f4d0a8c1e762"
down_revision: str | Sequence[str] | None = "e2b8c4f10593"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("career_runs", sa.Column("team", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("career_runs", "team")
