"""AI 멀티 에이전트 승부예측 테이블 추가

Revision ID: c5a2e91d7b34
Revises: b3f1c9d2a740
Create Date: 2026-08-04

기존 `ple_matches`의 `ai_pick`(20자)·`ai_pick_name`(200자)·`ai_correct` 세 컬럼으로는
승률·근거·에이전트별 리포트를 담을 자리가 없다
(`apps/kayfabe/_docs/ai-match-predictions-harness.md` §2-D5).

**기존 세 컬럼은 건드리지 않는다.** 적중률 집계(`get_ai_stats`)와 프론트 위젯이
그 컬럼을 읽고 있고, 에이전트가 전부 실패했을 때의 폴백 경로로도 계속 쓴다.

`ple_agent_reports`를 별도 테이블로 두는 이유는 리포트 수가 에이전트 수만큼 늘고
출처 URL을 각각 달고 다니기 때문이다. JSON 컬럼 하나로 뭉치면 "어느 에이전트가
무엇을 근거로 골랐나"를 SQL로 물어볼 수 없다.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c5a2e91d7b34"
down_revision: str | Sequence[str] | None = "b3f1c9d2a740"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ple_agent_predictions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("match_key", sa.String(length=80), nullable=False),
        sa.Column("pick", sa.String(length=20), nullable=False),
        sa.Column("pick_name", sa.String(length=200), nullable=False),
        sa.Column("win_probability", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=30), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["event_id"], ["ple_events.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        # 경기당 예측은 하나다. 재생성은 기존 행을 지우고 다시 넣는다.
        sa.UniqueConstraint("event_id", "match_key", name="uq_agent_prediction_match"),
    )
    op.create_index(
        op.f("ix_ple_agent_predictions_event_id"),
        "ple_agent_predictions",
        ["event_id"],
    )

    op.create_table(
        "ple_agent_reports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("prediction_id", sa.Integer(), nullable=False),
        sa.Column("agent", sa.String(length=30), nullable=False),
        # 의견 없음은 NULL이다 — 빈 문자열과 구분한다.
        sa.Column("pick", sa.String(length=20), nullable=True),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("sources", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["prediction_id"], ["ple_agent_predictions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_ple_agent_reports_prediction_id"),
        "ple_agent_reports",
        ["prediction_id"],
    )


def downgrade() -> None:
    """저장된 예측과 근거가 사라진다. 재생성은 LLM 비용이 다시 드는 작업이다."""
    op.drop_index(
        op.f("ix_ple_agent_reports_prediction_id"), table_name="ple_agent_reports"
    )
    op.drop_table("ple_agent_reports")
    op.drop_index(
        op.f("ix_ple_agent_predictions_event_id"), table_name="ple_agent_predictions"
    )
    op.drop_table("ple_agent_predictions")
