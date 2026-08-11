"""커리어 로그에 그 주차의 인기도·성향

Revision ID: c9a2e57b3184
Revises: b8f4d1c62073
Create Date: 2026-08-11

뉴스의 군중 반응과 턴 판정이 이 둘을 읽는다
(`apps/wwe_game/_docs/career-simulator-harness.md` §3-D39).

**저장하지 않던 시절 `compile_feed`는 30년치 반응을 마지막 스탯 하나로 계산했다** —
그 함수의 설명이 *"힐턴을 하기 전의 대관에도 야유가 붙는다"*고 경고하던 상황이 실제로
벌어지고 있었다. 로그에 스탯이 없어 호출자가 최종 스탯을 넘길 수밖에 없었다.

**스탯 여섯을 다 담지 않는다.** 읽는 것이 둘뿐이라 나머지는 로그를 키우기만 한다.

**nullable이다.** 이 마이그레이션 이전 행은 None이고, 그때는 예전처럼 최종 스탯으로
되돌아간다 — 옛 세이브의 뉴스가 조금 뭉개질 뿐 깨지지 않는다.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c9a2e57b3184"
down_revision: str | Sequence[str] | None = "b8f4d1c62073"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "career_log_entries", sa.Column("popularity", sa.Integer(), nullable=True)
    )
    op.add_column(
        "career_log_entries", sa.Column("alignment", sa.Integer(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("career_log_entries", "alignment")
    op.drop_column("career_log_entries", "popularity")
