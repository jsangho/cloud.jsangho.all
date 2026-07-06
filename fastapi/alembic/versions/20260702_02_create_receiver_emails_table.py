"""create receiver_emails table with embedding column

Revision ID: 20260702_02
Revises: 20260702_01
Create Date: 2026-07-02

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "20260702_02"
down_revision: str | None = "20260702_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EMBEDDING_DIM = 3072


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "receiver_emails",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("from_email", sa.String(length=255), nullable=False),
        sa.Column("from_name", sa.String(length=255), nullable=True),
        sa.Column("to_email", sa.String(length=255), nullable=True),
        sa.Column("subject", sa.String(length=500), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("message_id", sa.String(length=255), nullable=True),
        sa.Column(
            "receiver_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "spam_label", sa.String(length=32), nullable=False, server_default="ham"
        ),
        sa.Column("spam_confidence", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("receiver_emails")
