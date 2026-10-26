"""커리어 샌드박스 요청 영수증 표

Revision ID: c3d57e9b14af
Revises: f1a8d6c93b24
Create Date: 2026-10-21

처리가 끝난 쓰기 요청을 적는 표 하나. **세이브의 일부가 아니다.**

## 세이브 안에 넣지 않은 이유

`f1a8d6c93b24` 가 "표 하나, JSON 한 칸" 으로 간 것은 **세계**를 쪼개면
마이그레이션이 게임 규칙 수만큼 늘기 때문이었다. 영수증은 그 규칙에 걸리지
않는다 — 게임 규칙이 늘어도 칸이 늘지 않고(요청 id·지문·응답 셋이 전부),
반대로 세이브 안에 넣으면 세 가지가 깨진다.

    1. **보존 기간이 다르다.** 영수증은 버려도 되고 세이브는 못 버린다.
       `WorldState.applied` 같은 집합에 요청 키를 쌓으면 영원히 자란다.
    2. **고유 제약을 걸 수 없다.** JSON 안의 키는 DB 가 중복을 막아 주지 못한다.
    3. **응답 본문이 통째로 들어간다.** 세이브 JSON 이 수십 배로 부푼다.

## 고유 제약이 이 표의 요점이다

`(user_id, career_id, request_id)` 하나. 격리 둘을 동시에 만족시킨다 — 같은
사용자의 서로 다른 커리어, 서로 다른 사용자가 같은 키를 써도 섞이지 않는다.
`career_id` 만으로도 사용자가 정해지지만 `user_id` 를 함께 두는 것은 조회가 늘
사용자와 함께 걸리기 때문이다(이 앱의 소유권 규칙).

## 무한 누적을 막는 것은 코드다

보존 정책은 크론이 아니라 쓰기 경로다 — `SandboxCareerPgRepository.save` 가
영수증을 넣은 **같은 트랜잭션에서** 그 커리어의 오래된 것을 떨어뜨린다
(`RECEIPT_KEEP` 개만 남긴다). 그래서 이 마이그레이션에는 정리 작업이 없고,
운영에 돌릴 배치도 없다.

## 되돌리기

`downgrade()` 는 이 표만 떨어뜨린다. 영수증을 잃으면 **그 순간 전송 중이던
요청의 재시도가 다시 적용될 수 있다** — 되돌리기는 조용한 동작이 아니다.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "c3d57e9b14af"
down_revision: str | Sequence[str] | None = "f1a8d6c93b24"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sandbox_career_requests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("career_id", sa.Integer(), nullable=False),
        # 클라이언트가 만든 키. 화면은 `crypto.randomUUID()`(36자)를 쓴다.
        sa.Column("request_id", sa.String(length=64), nullable=False),
        # payload 의 sha256 hex — 64자 고정이다.
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        # JSONB 를 쓰는 것은 세이브와 같은 이유다. `JSON` 이면 Postgres 가 텍스트로
        # 들고 있어 나중에 안을 조회할 수단이 없다.
        sa.Column("response", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        # 세이브가 지워지면 영수증도 같이 간다. 남겨 둘 이유가 없다.
        sa.ForeignKeyConstraint(
            ["career_id"], ["sandbox_careers.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "career_id",
            "request_id",
            name="uq_sandbox_career_requests_scope",
        ),
    )
    # 보존 상한을 적용할 때 쓰는 인덱스 — "이 커리어의 최신 N 개".
    op.create_index(
        "ix_sandbox_career_requests_career_id",
        "sandbox_career_requests",
        ["career_id", "id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_sandbox_career_requests_career_id", table_name="sandbox_career_requests"
    )
    op.drop_table("sandbox_career_requests")
