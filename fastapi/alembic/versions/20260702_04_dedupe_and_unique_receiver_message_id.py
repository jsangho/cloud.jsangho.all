"""dedupe receiver_emails and add unique constraint on message_id

Revision ID: 20260702_04
Revises: 20260702_03
Create Date: 2026-07-02

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260702_04"
down_revision: str | None = "20260702_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Gmail Pub/Sub의 at-least-once 배달로 생긴 중복(message_id 동일) 행 중 가장 오래된 것만 남긴다.
    op.execute(
        """
        DELETE FROM receiver_emails a
        USING receiver_emails b
        WHERE a.message_id IS NOT NULL
          AND a.message_id = b.message_id
          AND a.id > b.id
        """
    )
    op.create_unique_constraint(
        "uq_receiver_emails_message_id", "receiver_emails", ["message_id"]
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_receiver_emails_message_id", "receiver_emails", type_="unique"
    )
