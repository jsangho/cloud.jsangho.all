"""add spam_label and spam_confidence to receiver_emails

Revision ID: 20260702_01
Revises: 20260701_03
Create Date: 2026-07-02

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260702_01"
down_revision: str | None = "20260701_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "receiver_emails",
        sa.Column(
            "spam_label", sa.String(length=32), nullable=False, server_default="ham"
        ),
    )
    op.add_column(
        "receiver_emails",
        sa.Column("spam_confidence", sa.Float(), nullable=False, server_default="1.0"),
    )


def downgrade() -> None:
    op.drop_column("receiver_emails", "spam_confidence")
    op.drop_column("receiver_emails", "spam_label")
