"""add contacts table

Revision ID: 20260701_01
Revises: 20260604_03
Create Date: 2026-07-01

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260701_01"
down_revision: str | None = "20260604_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "contacts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("given_name", sa.String(length=128), nullable=True),
        sa.Column("family_name", sa.String(length=128), nullable=True),
        sa.Column("nickname", sa.String(length=128), nullable=True),
        sa.Column("birthday", sa.String(length=32), nullable=True),
        sa.Column("gender", sa.String(length=32), nullable=True),
        sa.Column("occupation", sa.String(length=128), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("group_membership", sa.String(length=255), nullable=True),
        sa.Column("email_1_value", sa.String(length=255), nullable=True),
        sa.Column("email_2_value", sa.String(length=255), nullable=True),
        sa.Column("phone_1_value", sa.String(length=64), nullable=True),
        sa.Column("phone_2_value", sa.String(length=64), nullable=True),
        sa.Column("address_1_formatted", sa.Text(), nullable=True),
        sa.Column("address_1_street", sa.String(length=255), nullable=True),
        sa.Column("address_1_city", sa.String(length=128), nullable=True),
        sa.Column("address_1_region", sa.String(length=128), nullable=True),
        sa.Column("address_1_postal_code", sa.String(length=32), nullable=True),
        sa.Column("address_1_country", sa.String(length=128), nullable=True),
        sa.Column("org_name", sa.String(length=255), nullable=True),
        sa.Column("org_title", sa.String(length=128), nullable=True),
        sa.Column("org_department", sa.String(length=128), nullable=True),
        sa.Column("website_1_value", sa.String(length=512), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email_1_value", name="uq_contacts_email_1_value"),
    )
    op.create_index(
        op.f("ix_contacts_email_1_value"),
        "contacts",
        ["email_1_value"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_contacts_email_1_value"), table_name="contacts")
    op.drop_table("contacts")
