"""add to_email and message_id to receiver_emails

Revision ID: 20260701_03
Revises: 20260701_02
Create Date: 2026-07-01

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260701_03"
down_revision: str | None = "20260701_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "receiver_emails", sa.Column("to_email", sa.String(length=255), nullable=True)
    )
    op.add_column(
        "receiver_emails", sa.Column("message_id", sa.String(length=255), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("receiver_emails", "message_id")
    op.drop_column("receiver_emails", "to_email")
