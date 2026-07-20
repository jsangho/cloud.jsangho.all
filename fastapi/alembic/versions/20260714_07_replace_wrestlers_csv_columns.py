"""replace wrestlers columns for cleaned CSV source (wwe_active_roster_cleaned.csv)

Revision ID: 20260714_07
Revises: 20260714_06
Create Date: 2026-07-20

가정 사항 (apps/kayfabe/_docs/wwe-roster-database.md 3번 섹션 a~i):
- d. resides/debut/retired 컬럼은 신규 CSV(wwe_active_roster_cleaned.csv)에 아예 존재하지
  않는다. wikipedia_title도 마찬가지로 신규 CSV에 없다. 네 컬럼 모두 DROP한다.
- 신규 CSV에 있는 Stable&Team -> stable_team(VARCHAR(100)), 그리고 CSV의 #RAW/#SmackDown/
  #Free Agent/#NXT/#Evolve 브랜드 마커에서 파생하는 brand(VARCHAR(20))를 ADD한다.
- height/weight/birth_date/ring_names/trainer/embedding 등 나머지 컬럼 타입은 변경하지 않는다
  (20260714_05/06에서 이미 충분히 넓혀둔 상태).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260714_07"
down_revision: str | None = "20260714_06"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("wrestlers", "wikipedia_title")
    op.drop_column("wrestlers", "resides")
    op.drop_column("wrestlers", "debut")
    op.drop_column("wrestlers", "retired")
    op.add_column(
        "wrestlers", sa.Column("stable_team", sa.String(length=100), nullable=True)
    )
    op.add_column("wrestlers", sa.Column("brand", sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column("wrestlers", "brand")
    op.drop_column("wrestlers", "stable_team")
    op.add_column(
        "wrestlers", sa.Column("retired", sa.String(length=30), nullable=True)
    )
    op.add_column("wrestlers", sa.Column("debut", sa.String(length=30), nullable=True))
    op.add_column(
        "wrestlers", sa.Column("resides", sa.String(length=150), nullable=True)
    )
    op.add_column(
        "wrestlers", sa.Column("wikipedia_title", sa.String(length=255), nullable=True)
    )
