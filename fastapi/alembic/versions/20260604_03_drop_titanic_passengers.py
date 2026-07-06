"""drop titanic_passengers (use titanic_persons + titanic_bookings only)

Revision ID: 20260604_03
Revises: 20260604_02
Create Date: 2026-06-04

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260604_03"
down_revision: str | None = "20260604_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "titanic_passengers" not in inspector.get_table_names():
        return

    op.drop_index(
        op.f("ix_titanic_passengers_passenger_id"), table_name="titanic_passengers"
    )
    op.drop_table("titanic_passengers")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "titanic_passengers" in inspector.get_table_names():
        return

    op.create_table(
        "titanic_passengers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("passenger_id", sa.Integer(), nullable=False),
        sa.Column("survived", sa.Integer(), nullable=True),
        sa.Column("pclass", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("sex", sa.String(length=10), nullable=True),
        sa.Column("age", sa.Float(), nullable=True),
        sa.Column("sibsp", sa.Integer(), nullable=True),
        sa.Column("parch", sa.Integer(), nullable=True),
        sa.Column("ticket", sa.String(length=64), nullable=True),
        sa.Column("fare", sa.Float(), nullable=True),
        sa.Column("cabin", sa.String(length=32), nullable=True),
        sa.Column("embarked", sa.String(length=1), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("passenger_id"),
    )
    op.create_index(
        op.f("ix_titanic_passengers_passenger_id"),
        "titanic_passengers",
        ["passenger_id"],
        unique=False,
    )
