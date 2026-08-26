"""ple_agent_predictions에 표본 계보 두 칸 (Phase 3-7)

**시간 컬럼이 잘못된 것이 아니라, "답이 어디에 있었는가"를 아무도 적지 않았다.**
`ple_matches.finished_at`은 결과가 **DB에 기록된** 시각이라 시스템 밖의 앎 — 사람이
이미 아는 결과, 모델의 학습 데이터 — 을 담지 못한다. 그 사실을 예측 단위로 남긴다.

`NULL`은 "모른다"가 아니라 **"아무도 선언하지 않았다"** 는 뜻이다. 그래서 옛 행은
Phase 3-6의 판정 경로를 그대로 지나가고 판정이 한 건도 바뀌지 않는다. "모른다"를
말하려면 `false`로 명시한다.

`server_default`를 두지 않는 이유가 그것이다 — 기본값을 넣으면 옛 행이 "선언됨"이
되어 버린다.

Revision ID: a4c9e2f71b83
Revises: d3f5b81a29c4
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a4c9e2f71b83"
down_revision: str | Sequence[str] | None = "d3f5b81a29c4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 컬럼 추가만 한다. 기존 행은 UPDATE하지 않는다 — 옛 예측의 판정을 건드리지
    # 않는 것이 이 마이그레이션의 유일한 성공 기준이다.
    op.add_column(
        "ple_agent_predictions",
        sa.Column("outcome_known_externally", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "ple_agent_predictions",
        sa.Column("provenance_note", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    # 선언 값도 함께 사라진다 — 승인된 트레이드오프다(Phase 3-7 §5).
    op.drop_column("ple_agent_predictions", "provenance_note")
    op.drop_column("ple_agent_predictions", "outcome_known_externally")
