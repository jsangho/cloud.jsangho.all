"""make ple_events.month nullable (TBD-schedule PLEs)

Revision ID: 20260713_01
Revises: 20260702_04
Create Date: 2026-07-13

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260713_01"
down_revision: str | None = "20260702_04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("ple_events", "month", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    op.alter_column("ple_events", "month", existing_type=sa.Integer(), nullable=False)
