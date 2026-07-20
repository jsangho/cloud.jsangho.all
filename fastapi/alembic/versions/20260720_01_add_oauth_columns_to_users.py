"""add oauth_provider/oauth_id to users (Google 소셜 로그인)

Revision ID: 20260720_01
Revises: 20260714_06
Create Date: 2026-07-20
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260720_01"
down_revision: str | None = "20260714_06"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("oauth_provider", sa.String(), nullable=True))
    op.add_column("users", sa.Column("oauth_id", sa.String(), nullable=True))
    op.create_index(
        "ix_users_oauth_provider_oauth_id",
        "users",
        ["oauth_provider", "oauth_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_users_oauth_provider_oauth_id", table_name="users")
    op.drop_column("users", "oauth_id")
    op.drop_column("users", "oauth_provider")
