"""커리어 시뮬레이터 세이브 테이블 다섯 개

Revision ID: e2b8c4f10593
Revises: d1c7f3b80204
Create Date: 2026-08-07

`apps/wwe_game/_docs/career-simulator-harness.md` §6의 DB 엔티티다. 접두사는 `career_`로
통일한다 — kayfabe가 `ple_*`를 쓰는 것과 같은 이유.

**세이브 하나가 다섯 표에 걸쳐 있다.** 자식 넷은 전부 `career_runs.id`를 `ON DELETE
CASCADE`로 참조한다 — 커리어를 지우면 그 자취도 함께 사라져야 한다.

`titles_held`·`titles_won`·`flags`·`recent_events`는 표가 아니라 **JSON 칼럼**이다.
진행 한 번이 세이브를 통째로 다시 쓰므로(§3-D6), 순서 있는 512칸짜리 목록을 표로 빼면
저장마다 512행을 지웠다 다시 넣게 된다. 조회 단위도 아니다.

`career_runs`에 "사용자당 진행 중 하나"를 유니크로 걸지 않는다. 끝난 세이브까지 한 줄로
묶여 이력을 못 남기기 때문이고, 그 규칙은 유스케이스가 지킨다(§13-Q4).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e2b8c4f10593"
down_revision: str | Sequence[str] | None = "d1c7f3b80204"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RUN_FK = "career_runs.id"


def upgrade() -> None:
    op.create_table(
        "career_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=20), nullable=False),
        sa.Column("gender", sa.String(length=10), nullable=False),
        sa.Column("country", sa.String(length=10), nullable=False),
        sa.Column("play_style", sa.String(length=20), nullable=False),
        sa.Column("mode_code", sa.String(length=20), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("popularity", sa.Integer(), nullable=False),
        sa.Column("in_ring", sa.Integer(), nullable=False),
        sa.Column("mic_work", sa.Integer(), nullable=False),
        sa.Column("backstage", sa.Integer(), nullable=False),
        sa.Column("alignment", sa.Integer(), nullable=False),
        sa.Column("condition_grade", sa.String(length=20), nullable=False),
        sa.Column("condition_weeks_left", sa.Integer(), nullable=False),
        sa.Column("wear", sa.Integer(), nullable=False),
        sa.Column("pending_code", sa.String(length=60), nullable=True),
        sa.Column("pending_week", sa.Integer(), nullable=True),
        sa.Column("pending_body_index", sa.Integer(), nullable=True),
        sa.Column("pending_rival", sa.String(length=60), nullable=True),
        sa.Column("brand", sa.String(length=20), nullable=False),
        sa.Column("titles_held", sa.JSON(), nullable=False),
        sa.Column("titles_won", sa.JSON(), nullable=False),
        sa.Column("flags", sa.JSON(), nullable=False),
        sa.Column("recent_events", sa.JSON(), nullable=False),
        sa.Column("events_fired", sa.Integer(), nullable=False),
        sa.Column("release_weeks", sa.Integer(), nullable=False),
        sa.Column("decline_weeks", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("end_reason", sa.String(length=20), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_career_runs_user_id", "career_runs", ["user_id"])
    op.create_index("ix_career_runs_status", "career_runs", ["status"])
    op.create_index(
        "ix_career_runs_user_status", "career_runs", ["user_id", "status"]
    )

    op.create_table(
        "career_rivalries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("rival_name", sa.String(length=60), nullable=False),
        sa.Column("stage", sa.String(length=20), nullable=False),
        sa.Column("heat", sa.Integer(), nullable=False),
        sa.Column("started_week", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], [RUN_FK], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "rival_name", name="uq_career_rivalry"),
    )
    op.create_index("ix_career_rivalries_run_id", "career_rivalries", ["run_id"])

    op.create_table(
        "career_log_entries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("result", sa.String(length=10), nullable=True),
        sa.Column("show_name", sa.String(length=60), nullable=True),
        sa.Column("title_code", sa.String(length=60), nullable=True),
        sa.Column("narration", sa.String(length=400), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], [RUN_FK], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "week", name="uq_career_log_week"),
    )
    op.create_index("ix_career_log_entries_run_id", "career_log_entries", ["run_id"])
    op.create_index(
        "ix_career_log_run_week", "career_log_entries", ["run_id", "week"]
    )

    op.create_table(
        "career_seen_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=60), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], [RUN_FK], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "code", name="uq_career_seen_event"),
    )
    op.create_index("ix_career_seen_events_run_id", "career_seen_events", ["run_id"])

    op.create_table(
        "career_trophies",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=60), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], [RUN_FK], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "code", name="uq_career_trophy"),
    )
    op.create_index("ix_career_trophies_run_id", "career_trophies", ["run_id"])


def downgrade() -> None:
    for table in (
        "career_trophies",
        "career_seen_events",
        "career_log_entries",
        "career_rivalries",
        "career_runs",
    ):
        op.drop_table(table)
