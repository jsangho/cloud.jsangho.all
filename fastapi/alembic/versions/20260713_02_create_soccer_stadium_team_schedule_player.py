"""create soccer stadium, team, schedule, player tables

Revision ID: 20260713_02
Revises: 20260713_01
Create Date: 2026-07-13

가정 사항:
- ERD는 stadium_id / sche_date / team_id / player_id를 각 테이블의 PK로 표기하지만,
  프로젝트 표준(fastapi/_docs/ENTITY_RULE.md)에 따라 모든 테이블에 surrogate
  `id`(int, autoincrement) PK를 두고, ERD의 PK 컬럼은 unique 인덱스가 걸린
  비즈니스 식별자로 다룬다. FK는 이 비즈니스 식별자 컬럼을 참조한다.
- schedule.sche_date는 같은 날짜에 여러 경기가 존재할 수 있어 unique 제약을
  두지 않고 일반 인덱스만 부여한다.
- ERD에 ON DELETE 정책이 명시되어 있지 않아 모든 FK는 기본값(NO ACTION)을 사용한다.
- pgvector extension은 20260702_02 마이그레이션에서 이미 보장되어 있어 별도로
  추가하지 않는다.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260713_02"
down_revision: str | None = "20260713_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "stadium",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("stadium_id", sa.String(length=10), nullable=False),
        sa.Column("statdium_name", sa.String(length=40), nullable=True),
        sa.Column("hometeam_id", sa.String(length=10), nullable=True),
        sa.Column("seat_count", sa.Integer(), nullable=True),
        sa.Column("address", sa.String(length=60), nullable=True),
        sa.Column("ddd", sa.String(length=10), nullable=True),
        sa.Column("tel", sa.String(length=10), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_stadium_stadium_id"), "stadium", ["stadium_id"], unique=True
    )

    op.create_table(
        "team",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("team_id", sa.String(length=10), nullable=False),
        sa.Column("region_name", sa.String(length=10), nullable=True),
        sa.Column("team_name", sa.String(length=40), nullable=True),
        sa.Column("e_team_name", sa.String(length=50), nullable=True),
        sa.Column("orig_yyyy", sa.String(length=10), nullable=True),
        sa.Column("zip_code1", sa.String(length=10), nullable=True),
        sa.Column("zip_code2", sa.String(length=10), nullable=True),
        sa.Column("address", sa.String(length=80), nullable=True),
        sa.Column("ddd", sa.String(length=10), nullable=True),
        sa.Column("tel", sa.String(length=10), nullable=True),
        sa.Column("fax", sa.String(length=10), nullable=True),
        sa.Column("homepage", sa.String(length=50), nullable=True),
        sa.Column("owner", sa.String(length=10), nullable=True),
        sa.Column("stadium_id", sa.String(length=10), nullable=True),
        sa.ForeignKeyConstraint(["stadium_id"], ["stadium.stadium_id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_team_team_id"), "team", ["team_id"], unique=True)
    op.create_index(op.f("ix_team_stadium_id"), "team", ["stadium_id"], unique=False)

    op.create_table(
        "schedule",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("sche_date", sa.String(length=10), nullable=True),
        sa.Column("stadium_id", sa.String(length=10), nullable=True),
        sa.Column("gubun", sa.String(length=10), nullable=True),
        sa.Column("hometeam_id", sa.String(length=10), nullable=True),
        sa.Column("awayteam_id", sa.String(length=10), nullable=True),
        sa.Column("home_score", sa.Integer(), nullable=True),
        sa.Column("away_score", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["stadium_id"], ["stadium.stadium_id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_schedule_sche_date"), "schedule", ["sche_date"], unique=False
    )
    op.create_index(
        op.f("ix_schedule_stadium_id"), "schedule", ["stadium_id"], unique=False
    )

    op.create_table(
        "player",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("player_id", sa.String(length=10), nullable=False),
        sa.Column("player_name", sa.String(length=20), nullable=True),
        sa.Column("e_player_name", sa.String(length=40), nullable=True),
        sa.Column("nickname", sa.String(length=30), nullable=True),
        sa.Column("join_yyyy", sa.String(length=10), nullable=True),
        sa.Column("position", sa.String(length=10), nullable=True),
        sa.Column("back_no", sa.Integer(), nullable=True),
        sa.Column("nation", sa.String(length=20), nullable=True),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column("solar", sa.String(length=10), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("weight", sa.Integer(), nullable=True),
        sa.Column("team_id", sa.String(length=10), nullable=True),
        sa.ForeignKeyConstraint(["team_id"], ["team.team_id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_player_player_id"), "player", ["player_id"], unique=True)
    op.create_index(op.f("ix_player_team_id"), "player", ["team_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_player_team_id"), table_name="player")
    op.drop_index(op.f("ix_player_player_id"), table_name="player")
    op.drop_table("player")

    op.drop_index(op.f("ix_schedule_stadium_id"), table_name="schedule")
    op.drop_index(op.f("ix_schedule_sche_date"), table_name="schedule")
    op.drop_table("schedule")

    op.drop_index(op.f("ix_team_stadium_id"), table_name="team")
    op.drop_index(op.f("ix_team_team_id"), table_name="team")
    op.drop_table("team")

    op.drop_index(op.f("ix_stadium_stadium_id"), table_name="stadium")
    op.drop_table("stadium")
