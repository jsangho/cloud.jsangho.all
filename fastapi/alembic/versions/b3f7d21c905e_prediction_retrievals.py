"""예측 검색 기록 (Phase 3-13 Stage 4)

**출처 URL만으로는 무엇을 읽었는지 말할 수 없다.** `ple_agent_reports.sources`에
남는 것은 URL이고, 위키 문서는 경기 전후로 계속 개정된다 — 같은 주소라도 우리가
읽은 개정본이 경기 앞인지 뒤인지가 판정을 가른다. 그 기록이 없어서 Phase 3-12의
판정은 문서 단위로, 그 문서의 **가장 늦은** 개정본을 기준으로 잡을 수밖에 없었다
(`_corpus`의 최악 기준). 이 테이블이 그 자리를 메운다.

**청크에 FK를 걸지 않는다.** 재수집은 그 URL의 옛 청크를 통째로 DELETE한 뒤 새로
넣으므로(`replace_document_chunks`), 참조로 두면 코퍼스를 다시 모으는 순간 기록이
가리키는 행이 사라진다. 증거가 필요한 바로 그 시점에 증거가 없어지는 설계다.
그래서 그때 값을 베껴 둔다 — 비정규화가 아니라 **스냅샷**이다. `chunk_id`는 참조가
아니라 당시 식별자를 적어 둔 칸이라 FK도 인덱스도 걸지 않는다.

**예측에는 FK를 건다**(`ON DELETE CASCADE`). 기록은 그 생성에 속하고, 재생성이
예측 행을 갈아 끼우므로 옛 생성의 기록이 새 예측에 남아서는 안 된다.

**기존 19건은 이 테이블에 행이 없다.** 백필하지 않는다 — 그때 무엇을 읽었는지는
아무도 모르고, 지금 코퍼스에서 다시 검색해 채우면 "그때 읽은 것"이 아니라 "지금
검색되는 것"을 적는 것이 된다. 빈 것이 정직한 상태다. 판정(`_corpus`)은 이번
변경에서 손대지 않으므로 옛 예측의 버킷도 그대로다.

Revision ID: b3f7d21c905e
Revises: e5b7c1d924af
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b3f7d21c905e"
down_revision: str | Sequence[str] | None = "e5b7c1d924af"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ple_prediction_retrievals",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("prediction_id", sa.Integer(), nullable=False),
        # 프롬프트에 들어간 순서(1부터). 검색 순위가 아니라 **읽은 순서**다 —
        # 선정은 거리로 하고 늘어놓는 것은 최신순이라 둘이 어긋날 수 있다.
        sa.Column("rank", sa.Integer(), nullable=False),
        # 당시 청크 행의 id. 참조가 아니므로 FK를 걸지 않는다.
        sa.Column("chunk_id", sa.Integer(), nullable=True),
        sa.Column("source_url", sa.String(length=500), nullable=True),
        # 본문 sha256. 재수집 뒤에도 같은 글인지 대조할 수 있는 유일한 값이다.
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column("source_revision_id", sa.String(length=64), nullable=True),
        sa.Column(
            "source_revised_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        # 코사인 거리. 못 구하면 NULL — 0.0으로 채우지 않는다.
        sa.Column("distance", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["prediction_id"],
            ["ple_agent_predictions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "prediction_id", "rank", name="uq_prediction_retrieval_rank"
        ),
    )
    op.create_index(
        op.f("ix_ple_prediction_retrievals_prediction_id"),
        "ple_prediction_retrievals",
        ["prediction_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_ple_prediction_retrievals_prediction_id"),
        table_name="ple_prediction_retrievals",
    )
    op.drop_table("ple_prediction_retrievals")
