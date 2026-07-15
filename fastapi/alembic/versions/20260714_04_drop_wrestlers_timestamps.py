"""drop wrestlers.created_at/updated_at (not needed, CSV has no timestamp data)

Revision ID: 20260714_04
Revises: 20260714_03
Create Date: 2026-07-14

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260714_04"
down_revision: str | None = "20260714_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("wrestlers", "updated_at")
    op.drop_column("wrestlers", "created_at")


def downgrade() -> None:
    op.add_column(
        "wrestlers",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.add_column(
        "wrestlers",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
