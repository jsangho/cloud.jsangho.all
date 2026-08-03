"""users.email nullable — 카카오 이메일 미동의 계정의 모바일 로그인 허용

Revision ID: b3f1c9d2a740
Revises: 07a11683a53b
Create Date: 2026-08-03

카카오 이메일은 선택 동의 항목이라 동의하지 않은 계정에는 값이 없다. `users.email`이
NOT NULL인 동안에는 그런 계정의 모바일 로그인이 유저 생성 단계에서 실패한다
(하네스 §4-G). 플레이스홀더 이메일을 만들어 넣는 우회는 실제 주소와 충돌할 수 있어
채택하지 않았다.

UNIQUE 제약은 그대로 둔다. PostgreSQL의 UNIQUE 인덱스는 NULL을 서로 다른 값으로
취급하므로(PG15의 NULLS NOT DISTINCT를 명시하지 않는 한) 이메일이 없는 계정이
여러 개 있어도 충돌하지 않는다. 하네스 문서가 언급한 partial unique index는
이 동작 때문에 불필요하다.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b3f1c9d2a740"
down_revision: str | Sequence[str] | None = "07a11683a53b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "users",
        "email",
        existing_type=sa.String(),
        nullable=True,
    )


def downgrade() -> None:
    """이미 NULL인 행이 있으면 실패한다 — 이메일을 되살릴 방법이 없으므로 의도된 동작이다."""
    op.alter_column(
        "users",
        "email",
        existing_type=sa.String(),
        nullable=False,
    )
