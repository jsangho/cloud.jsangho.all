"""코퍼스 리비전 계보 + 대회 날짜 (Phase 3-12)

**`published_at`으로는 위키를 잴 수 없다.** 위키피디아는 `article:published_time`
계열 메타태그를 내보내지 않아 668청크가 전부 `NULL`이었고, 설령 채운다 해도 그 값은
문서 최초 생성일에 가까워 "이 문서가 경기 결과를 담고 있었는가"에 답하지 못한다.
같은 URL이 경기 전후로 계속 개정되기 때문이다.

그래서 축을 **리비전**으로 옮긴다. `source_revised_at`은 우리가 실제로 읽은 그
개정본이 만들어진 시각이고, `ple_events.start_date`와 비교해 "그 개정본이 경기보다
앞선다"를 증명한다. 앞선다면 결과가 적혀 있을 수 없다 — 충분조건이다.

**`published_at`은 지우지 않는다.** 뜻이 다른 값이고, 위키 아닌 소스가 들어오면
그때 제 일을 한다.

**넷 다 nullable이다.** 기존 668청크와 11개 대회는 이 값을 모르는 채로 남고,
`NULL`은 "모른다"이지 "통과"가 아니다 — 판정 쪽에서 그렇게 읽는다.
`server_default`를 두지 않는 이유도 같다. 기본값을 넣으면 옛 행이 "계보 있음"이
되어 버린다.

Revision ID: e5b7c1d924af
Revises: a4c9e2f71b83
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e5b7c1d924af"
down_revision: str | Sequence[str] | None = "a4c9e2f71b83"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 컬럼 추가만 한다. 기존 행은 UPDATE하지 않는다 — 옛 예측의 판정을 건드리지
    # 않는 것이 이 마이그레이션의 성공 기준이다(Phase 3-7과 같은 원칙).
    op.add_column(
        "ple_knowledge_chunks",
        sa.Column("source_revision_id", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "ple_knowledge_chunks",
        sa.Column("source_revised_at", sa.DateTime(timezone=True), nullable=True),
    )
    # 판정이 이 컬럼으로 문서를 고르므로 인덱스를 둔다 — `published_at`과 같은 대우다.
    op.create_index(
        "ix_ple_knowledge_chunks_source_revised_at",
        "ple_knowledge_chunks",
        ["source_revised_at"],
    )

    # **`DATE`다.** 우리가 가진 것은 날짜뿐이고, 없는 시각 정밀도를 지어내지 않는다.
    # 2일 대회(WrestleMania 4.18–19 · SummerSlam 8.1–2)를 담으려고 끝날도 둔다.
    # 다만 판정이 보는 것은 `start_date` 하나다 — 시작 전 개정본이면 둘째 날 결과도
    # 있을 수 없으므로 그쪽이 더 보수적이다.
    op.add_column("ple_events", sa.Column("start_date", sa.Date(), nullable=True))
    op.add_column("ple_events", sa.Column("end_date", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("ple_events", "end_date")
    op.drop_column("ple_events", "start_date")
    op.drop_index(
        "ix_ple_knowledge_chunks_source_revised_at",
        table_name="ple_knowledge_chunks",
    )
    op.drop_column("ple_knowledge_chunks", "source_revised_at")
    op.drop_column("ple_knowledge_chunks", "source_revision_id")
