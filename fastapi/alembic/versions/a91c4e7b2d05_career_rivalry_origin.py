"""career_rivalries에 누가 걸었는지 (하네스 §3-D86)

**옛 행은 전부 `rival`이다** — §3-D86 이전의 대립은 규칙이 열었고, 그것은
상대가 나를 지목해 온 것이다. 그래서 server_default가 곧 옛 세계의 진실이다.

Revision ID: a91c4e7b2d05
Revises: f4a72b9e31d0
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a91c4e7b2d05"
down_revision: str | Sequence[str] | None = "f4a72b9e31d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "career_rivalries",
        sa.Column(
            "opened_by", sa.String(length=10), nullable=False, server_default="rival"
        ),
    )


def downgrade() -> None:
    op.drop_column("career_rivalries", "opened_by")
