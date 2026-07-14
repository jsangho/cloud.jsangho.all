"""create wrestlers table (WWE active roster, CSV-derived schema)

Revision ID: 20260714_01
Revises: 20260713_02
Create Date: 2026-07-14

가정 사항 (apps/kayfabe/_docs/wwe-roster-database.md 3번 섹션 a~e):
- a. height/weight/birth_date/debut/retired는 원본 CSV 형식이 통일되어 있지 않아
  (단위 혼재, 연도만 있는 경우 등) INTEGER/DATE로 강제 변환하지 않고 원문 그대로
  VARCHAR/TEXT로 저장한다.
- b. ring_names/trainer는 스크래핑 과정에서 여러 값이 구분자 없이 이어붙은 상태로
  수집되었다. 원본 그대로 TEXT로 저장하며, 값 분리는 별도 데이터 정제 스크립트의
  책임으로 둔다.
- c. wikipedia_title은 위키 문서가 없는 선수의 경우 sentinel 문자열이 들어갈 수
  있어 UNIQUE 제약을 적용하지 않는다.
- d. resides 컬럼은 현재 CSV 197행 전체가 결측(NULL)이지만, 컬럼은 유지하고
  전량 NULL을 허용한다.
- e. embedding은 CSV에는 없으나 RAG 검색용으로 선제 추가한다. 차원은 문서 원안의
  1536(OpenAI 가정) 대신, 이 프로젝트가 이미 사용 중인 표준
  core.matrix.vault_keymaker_secret_manager.EMBEDDING_DIM(1024, bge-m3)을 따른다
  (receiver_emails 테이블과 동일 컨벤션, 사용자 확인 완료).
- pgvector extension은 20260702_02 마이그레이션에서 이미 보장되어 있어 별도로
  추가하지 않는다.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op

revision: str = "20260714_01"
down_revision: str | None = "20260713_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EMBEDDING_DIM = 1024


def upgrade() -> None:
    op.create_table(
        "wrestlers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("wikipedia_title", sa.String(length=255), nullable=True),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("real_name", sa.String(length=200), nullable=True),
        sa.Column("ring_names", sa.Text(), nullable=True),
        sa.Column("height", sa.String(length=20), nullable=True),
        sa.Column("weight", sa.String(length=20), nullable=True),
        sa.Column("birth_date", sa.String(length=30), nullable=True),
        sa.Column("birth_place", sa.String(length=150), nullable=True),
        sa.Column("resides", sa.String(length=150), nullable=True),
        sa.Column("billed_from", sa.String(length=150), nullable=True),
        sa.Column("trainer", sa.Text(), nullable=True),
        sa.Column("debut", sa.String(length=30), nullable=True),
        sa.Column("retired", sa.String(length=30), nullable=True),
        sa.Column("finisher", sa.Text(), nullable=True),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("wrestlers")
