"""커리어 샌드박스 세이브 표 하나

Revision ID: f1a8d6c93b24
Revises: b9c4e7a21f30
Create Date: 2026-10-20

표 **하나**다. 세계 전체가 `world` JSONB 한 칸에 들어간다 — 모양은
`kayfabe/adapter/outbound/pg/career_world_codec.py` 가 정한다.

## 옛 `career_*` 다섯 표를 건드리지 않는다

2026-08-07 의 `e2b8c4f10593` 이 만든 `career_runs`·`career_rivalries`·
`career_log_entries`·`career_seen_events`·`career_trophies` 는 **그대로 둔다.**
그 뒤로 ALTER 마이그레이션이 열한 개 더 붙었고(피니셔·계약·상금·부상 부위·
토너먼트 등), 담당 앱(`wwe_game`)은 2026-09-28 에 삭제됐지만 **표와 약 62행의
플레이 기록은 남아 있다.**

지우지 않는 이유는 둘이다. 첫째, 운영 DB 에 대한 파괴적 변경은 이 작업의 범위가
아니다. 둘째, 그 표의 스키마는 삭제된 40주 설계에 맞춰져 있어(시즌·나이 칸이
없다) 재사용하면 ALTER 가 다시 줄줄이 붙는다 — 새 표 하나가 더 싸고 비파괴적이다.

그래서 접두사도 `career_` 가 아니라 `sandbox_` 다. 이름이 겹치면 어느 쪽이
현행인지 쿼리를 열어 봐야 알게 된다.

## 되돌리기

`downgrade()` 는 이 표만 떨어뜨린다. 옛 표는 이 리비전이 만든 것이 아니므로
손대지 않는다.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "f1a8d6c93b24"
down_revision: str | Sequence[str] | None = "b9c4e7a21f30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sandbox_careers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("player_name", sa.String(length=40), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("week", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "phase", sa.String(length=20), nullable=False, server_default="in_season"
        ),
        # JSONB 를 쓰는 것은 의도다. `JSON` 이면 Postgres 가 텍스트로 들고 있어
        # 나중에 세이브 안을 조회할 수단이 없다.
        sa.Column("world", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sandbox_careers_user_id", "sandbox_careers", ["user_id"])
    # 목록은 "내 커리어를 최근 것부터" 로 읽는다.
    op.create_index(
        "ix_sandbox_careers_user_updated",
        "sandbox_careers",
        ["user_id", sa.text("updated_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_sandbox_careers_user_updated", table_name="sandbox_careers")
    op.drop_index("ix_sandbox_careers_user_id", table_name="sandbox_careers")
    op.drop_table("sandbox_careers")
