"""비선수 인원 표 (`wwe_staff`)

생일 보드가 해설·심판·경영진까지 세려고 만든 표다. 원본 CSV
(`apps/kayfabe/_docs/wwe_non_wrestler.csv`)는 저장소에 2026-07부터 있었지만
**적재한 적이 한 번도 없었다** — 테이블도 로더도 참조도 없는 고아 파일이었다.

**`wrestlers`에 합치지 않은 이유**는 `staff_orm.py` 독스트링에 적었다: 그 표에는
전적·예측·임베딩이 매달려 있어서, 경기에 나오지 않는 사람을 넣으면 선수 수와 전적
집계가 함께 틀어진다.

**`CREATE TABLE` 하나뿐이라 기존 코드가 도는 중에 올려도 안전하다.** 읽는 코드가
없는 동안에는 빈 표일 뿐이고, 되돌릴 때도 쓰는 쪽이 없으면 표만 남겨 두면 된다.

Revision ID: b9c4e7a21f30
Revises: a3f61c2d9e48
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b9c4e7a21f30"
down_revision: str | Sequence[str] | None = "a3f61c2d9e48"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "wwe_staff",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("real_name", sa.String(length=200), nullable=True),
        sa.Column("ring_name", sa.String(length=150), nullable=True),
        sa.Column("korean_ring_name", sa.String(length=150), nullable=True),
        sa.Column("role", sa.String(length=200), nullable=True),
        sa.Column("gender", sa.String(length=10), nullable=True),
        sa.Column("birth_date", sa.String(length=50), nullable=True),
        sa.Column("birth_place", sa.String(length=150), nullable=True),
        sa.Column("wrestling_experience", sa.String(length=100), nullable=True),
        sa.Column("wrestler_team_stable", sa.Text(), nullable=True),
        sa.Column("group_label", sa.String(length=50), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_wwe_staff_name"), "wwe_staff", ["name"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_wwe_staff_name"), table_name="wwe_staff")
    op.drop_table("wwe_staff")
