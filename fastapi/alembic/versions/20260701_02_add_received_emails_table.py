"""add receiver_emails table

Revision ID: 20260701_02
Revises: 20260701_01
Create Date: 2026-07-01

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260701_02"
down_revision: str | None = "20260701_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "receiver_emails",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("from_email", sa.String(length=255), nullable=False),
        sa.Column("from_name", sa.String(length=255), nullable=True),
        sa.Column("subject", sa.String(length=500), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column(
            "receiver_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default="false"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("receiver_emails")
