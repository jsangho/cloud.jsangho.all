"""계약과 돈

Revision ID: a7f31c9d0b48
Revises: e5c74a29b1f6
Create Date: 2026-08-11

계약·돈 (`apps/wwe_game/_docs/career-simulator-harness.md` §3-D47·D50).

- `money` — 잔액(달러). 주급이 매주 쌓인다
- `contract_pay` · `contract_signed_week` · `contract_ends_week` — 계약 한 장
- `unsigned_weeks` — 계약 없이 보낸 연속 주차

계약 세 칼럼은 **함께 있거나 함께 없다.** 없으면 무소속이고, 무소속은 인디를 뛴다.
방출이 커리어를 닫지 않게 된 것이 이 개정의 핵심이다 — 잘리는 것과 끝나는 것이
갈렸고, 끝나는 쪽은 `unsigned_weeks`가 센다.

**옛 세이브는 계약 없이 읽힌다.** 소급해 채우지 않는 이유: "그때 몸값이 얼마였는가"를
지금 스탯으로 지어내야 하고, 그렇게 만든 수치는 아무 근거가 없다. 무소속으로 시작해
복귀 오퍼를 굴리는 편이 규칙에 맞다 — 2년 유예 안에 거의 다 다시 계약한다.

`money`가 `BigInteger`인 이유: 30년 정상급이면 주 $9만 × 1560주다. `Integer`(21억)에
닿지는 않지만 여유를 두지 않을 이유도 없다.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a7f31c9d0b48"
down_revision: str | Sequence[str] | None = "e5c74a29b1f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "career_runs",
        sa.Column("money", sa.BigInteger(), nullable=False, server_default="0"),
    )
    op.add_column(
        "career_runs",
        sa.Column(
            "unsigned_weeks", sa.Integer(), nullable=False, server_default="0"
        ),
    )
    op.add_column("career_runs", sa.Column("contract_pay", sa.Integer(), nullable=True))
    op.add_column(
        "career_runs", sa.Column("contract_signed_week", sa.Integer(), nullable=True)
    )
    op.add_column(
        "career_runs", sa.Column("contract_ends_week", sa.Integer(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("career_runs", "contract_ends_week")
    op.drop_column("career_runs", "contract_signed_week")
    op.drop_column("career_runs", "contract_pay")
    op.drop_column("career_runs", "unsigned_weeks")
    op.drop_column("career_runs", "money")
