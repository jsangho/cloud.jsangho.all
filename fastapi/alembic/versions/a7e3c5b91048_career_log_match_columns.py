"""커리어 로그에 상대·경기 형식·탈락 요약 세 칸

Revision ID: a7e3c5b91048
Revises: f4d0a8c1e762
Create Date: 2026-08-11

로그가 지금까지 **주차·종류·결과·대회·타이틀·문장**만 담아서, 세이브를 다시 열면
그 주차가 로열럼블이었는지 싱글이었는지 알 수 없었다
(`apps/wwe_game/_docs/career-simulator-harness.md` §3-D32·D34).

- `opponent`·`match_kind` — 다시 연 로그가 **진행 중인 화면과 같은 줄**을 그린다
- `match_summary` — 럼블·챔버의 한 줄 요약("17번으로 입장 · 3명 탈락 · 22번째 탈락")

**비트 전체는 저장하지 않는다.** 럼블 하나가 입장 30 + 탈락 29 = 59줄이라 표로 빼면
커리어당 2천 줄이 쌓인다. 전체 타임라인은 그 '다음'을 누른 화면에만 살고, 요약만
남는다 (2026-08-11 사용자 결정).

**셋 다 nullable이다.** 경기 없는 주차(프로모·결장)에는 상대도 형식도 없고, 탈락이
없는 경기에는 요약이 없다. 이 마이그레이션 이전 로그도 전부 None으로 읽힌다.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a7e3c5b91048"
down_revision: str | Sequence[str] | None = "f4d0a8c1e762"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "career_log_entries", sa.Column("opponent", sa.String(60), nullable=True)
    )
    op.add_column(
        "career_log_entries", sa.Column("match_kind", sa.String(30), nullable=True)
    )
    op.add_column(
        "career_log_entries", sa.Column("match_summary", sa.String(120), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("career_log_entries", "match_summary")
    op.drop_column("career_log_entries", "match_kind")
    op.drop_column("career_log_entries", "opponent")
