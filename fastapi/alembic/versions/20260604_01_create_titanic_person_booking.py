"""create titanic_persons and titanic_bookings

Revision ID: 20260604_01
Revises:
Create Date: 2026-06-04

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260604_01"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "titanic_persons",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("passenger_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("gender", sa.String(length=10), nullable=True),
        sa.Column("age", sa.Float(), nullable=True),
        sa.Column("sib_sp", sa.Integer(), nullable=True),
        sa.Column("parch", sa.Integer(), nullable=True),
        sa.Column("survived", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("passenger_id"),
    )
    op.create_index(
        op.f("ix_titanic_persons_passenger_id"),
        "titanic_persons",
        ["passenger_id"],
        unique=False,
    )

    op.create_table(
        "titanic_bookings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("person_id", sa.Integer(), nullable=False),
        sa.Column("pclass", sa.Integer(), nullable=True),
        sa.Column("ticket", sa.String(length=64), nullable=True),
        sa.Column("fare", sa.Float(), nullable=True),
        sa.Column("cabin", sa.String(length=32), nullable=True),
        sa.Column("embarked", sa.String(length=1), nullable=True),
        sa.ForeignKeyConstraint(
            ["person_id"],
            ["titanic_persons.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("person_id", name="uq_titanic_bookings_person_id"),
    )
    op.create_index(
        op.f("ix_titanic_bookings_person_id"),
        "titanic_bookings",
        ["person_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_titanic_bookings_person_id"), table_name="titanic_bookings")
    op.drop_table("titanic_bookings")
    op.drop_index(op.f("ix_titanic_persons_passenger_id"), table_name="titanic_persons")
    op.drop_table("titanic_persons")
