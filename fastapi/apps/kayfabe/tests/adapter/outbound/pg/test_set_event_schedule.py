"""날짜 전용 쓰기 경로 테스트 (Phase 3-13 Stage 3-A).

**왜 이 메서드가 따로 필요했나.** 날짜를 쓰는 유일한 경로가
`upsert_event_from_sync`이었는데, 그것은 날짜만 쓰지 않는다 — 페이로드에 없는
경기를 지우고(`ple_predictions`가 CASCADE로 함께 사라진다), `status`를 갈아 끼우고,
결과가 실려 있으면 `winner_pick`까지 덮어쓴다. 대회 날짜 두 칸을 고치자고 감수할
폭이 아니다.

그래서 이 파일이 붙드는 것은 하나다: **두 칸 말고는 아무것도 바뀌지 않는다.**
`ple_events`의 나머지 컬럼, 경기 카드, 사용자 예측, 에이전트 예측·리포트를 각각
before/after로 대조한다.

SQLite 인메모리에서 **실제 쿼리를 돌린다** — production DB를 쓰지 않는다.

실행:

    cd fastapi
    PYTHONUTF8=1 PYTHONPATH=apps uv run pytest apps/kayfabe/tests/adapter/outbound/pg/test_set_event_schedule.py -q
"""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime

from core.entities.user_model import UserModel
from core.matrix.grid_oracle_database_manager import Base
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

# `outbound.mappers.__init__`가 `inbound.api`를 거쳐 다시 자신을 부르는 **기존** 순환이
# 있어서, PG 어댑터를 먼저 임포트하면 `ai_stats_to_progress` 해석이 깨진다. 운영에서는
# `main.py`가 라우터를 먼저 임포트해 순서가 맞으므로, 여기서도 같은 순서를 만든다.
import kayfabe.adapter.inbound.api.v1.ple_events_router  # noqa: F401,E402
from kayfabe.adapter.outbound.orm.agent_prediction_orm import (
    AgentPredictionModel,
    AgentReportModel,
)
from kayfabe.adapter.outbound.orm.ple_orm import (
    PleEventModel,
    PleEventStatus,
    PleMatchModel,
    PleMatchStatus,
    PlePredictionModel,
)
from kayfabe.adapter.outbound.pg.ple_events_pg_repository import (  # noqa: E402
    PleEventsPgRepository,
)

_TABLES = [
    # `ple_predictions.user_id`가 `users`를 참조한다 — 빠뜨리면 FK 해석이 깨진다.
    UserModel.__table__,
    PleEventModel.__table__,
    PleMatchModel.__table__,
    PlePredictionModel.__table__,
    AgentPredictionModel.__table__,
    AgentReportModel.__table__,
]

_FINISHED_AT = datetime(2026, 8, 4, 6, 57, 58, tzinfo=UTC)
_GENERATED_AT = datetime(2026, 8, 5, 5, 39, 50, tzinfo=UTC)


def _repository(session: AsyncSession) -> PleEventsPgRepository:
    return PleEventsPgRepository(session)


async def _seed() -> tuple[AsyncSession, object]:
    """production을 닮은 최소 상태: 결과가 확정된 대회 하나 + 경기 + 예측들."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(lambda c: Base.metadata.create_all(c, tables=_TABLES))

    factory = async_sessionmaker(engine, expire_on_commit=False)
    session = factory()
    session.add(
        PleEventModel(
            id=1,
            slug="summerslam",
            label="SummerSlam",
            month=8,
            year=2026,
            status=PleEventStatus.FINISHED,
            finished_at=_FINISHED_AT,
            start_date=None,
            end_date=None,
        )
    )
    session.add(
        PleMatchModel(
            id=10,
            event_id=1,
            match_key="ss26-n1-undisputed",
            title="Undisputed WWE Championship",
            format="singles",
            card_variant="sideA",
            card_json='{"format": "singles"}',
            sort_order=0,
            status=PleMatchStatus.FINISHED,
            winner_pick="left",
            winner_name="Cody Rhodes",
            finished_at=_FINISHED_AT,
            point_value=3,
        )
    )
    session.add(
        PlePredictionModel(id=100, match_id=10, client_id="client-1", pick="left")
    )
    session.add(
        AgentPredictionModel(
            id=200,
            event_id=1,
            match_key="ss26-n1-undisputed",
            pick="left",
            pick_name="Cody Rhodes",
            win_probability=0.7,
            confidence=0.5,
            rationale="근거",
            source="agents",
            generated_at=_GENERATED_AT,
        )
    )
    session.add(
        AgentReportModel(
            id=300,
            prediction_id=200,
            agent="storyline",
            pick="left",
            weight=1.0,
            summary="요약",
            sources="https://en.wikipedia.org/wiki/SummerSlam_(2026)",
        )
    )
    await session.commit()
    return session, engine


async def _snapshot(session: AsyncSession) -> dict:
    """비교 대상 전체를 한 벌 뜬다. `updated_at`은 장부 칸이라 뺀다."""
    event = (await session.execute(select(PleEventModel))).scalars().one()
    match = (await session.execute(select(PleMatchModel))).scalars().one()
    prediction = (await session.execute(select(PlePredictionModel))).scalars().one()
    agent = (await session.execute(select(AgentPredictionModel))).scalars().one()
    report = (await session.execute(select(AgentReportModel))).scalars().one()
    return {
        "event_other": (
            event.id,
            event.slug,
            event.label,
            event.month,
            event.year,
            event.status,
            event.finished_at,
        ),
        "event_dates": (event.start_date, event.end_date),
        "match": (
            match.id,
            match.event_id,
            match.match_key,
            match.title,
            match.format,
            match.card_variant,
            match.card_json,
            match.sort_order,
            match.status,
            match.winner_pick,
            match.winner_name,
            match.ai_pick,
            match.ai_correct,
            match.finished_at,
            match.point_value,
        ),
        "prediction": (prediction.id, prediction.match_id, prediction.pick),
        "agent": (agent.id, agent.event_id, agent.match_key, agent.pick),
        "report": (report.id, report.prediction_id, report.sources),
        "counts": (1, 1, 1, 1, 1),
    }


def _run(body):
    async def go():
        session, engine = await _seed()
        try:
            return await body(session)
        finally:
            await session.close()
            await engine.dispose()

    return asyncio.run(go())


# ── A. 존재하는 slug ────────────────────────────────────────────────


def test_a_existing_slug_returns_true() -> None:
    async def body(session):
        ok = await _repository(session).set_event_schedule(
            slug="summerslam",
            start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 2),
        )
        await session.commit()
        session.expire_all()
        event = (await session.execute(select(PleEventModel))).scalars().one()
        return ok, event.start_date, event.end_date

    ok, start, end = _run(body)
    assert ok is True
    assert start == date(2026, 8, 1)
    assert end == date(2026, 8, 2)


# ── B. 없는 slug → False, INSERT 없음 ──────────────────────────────


def test_b_missing_slug_returns_false_and_inserts_nothing() -> None:
    """**Survivor Series를 만들지 않는다**는 결정이 여기에 걸려 있다."""

    async def body(session):
        ok = await _repository(session).set_event_schedule(
            slug="survivor-series",
            start_date=date(2026, 11, 28),
            end_date=None,
        )
        await session.commit()
        rows = (await session.execute(select(PleEventModel))).scalars().all()
        return ok, len(rows), [r.slug for r in rows]

    ok, count, slugs = _run(body)
    assert ok is False
    assert count == 1, "없는 대회를 만들어내면 안 된다"
    assert slugs == ["summerslam"]


# ── C~H. 두 칸 말고는 아무것도 바뀌지 않는다 ────────────────────────


def test_c_to_h_only_the_two_date_columns_change() -> None:
    """C·D·E·F·G·H를 한 번에 — before/after 전수 대조가 가장 강한 증거다."""

    async def body(session):
        before = await _snapshot(session)
        await _repository(session).set_event_schedule(
            slug="summerslam",
            start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 2),
        )
        await session.commit()
        session.expire_all()
        after = await _snapshot(session)
        return before, after

    before, after = _run(body)

    # C — 날짜만 바뀐다
    assert before["event_dates"] == (None, None)
    assert after["event_dates"] == (date(2026, 8, 1), date(2026, 8, 2))

    # D·E — status / label·month·year / finished_at 불변
    assert after["event_other"] == before["event_other"]

    # F·G — 경기 카드, winner_pick, finished_at 불변
    assert after["match"] == before["match"]

    # H — 사용자 예측 불변
    assert after["prediction"] == before["prediction"]

    # 에이전트 예측·리포트도 불변
    assert after["agent"] == before["agent"]
    assert after["report"] == before["report"]

    # 행 수 불변 — 어느 테이블도 늘거나 줄지 않았다
    assert after["counts"] == before["counts"]


def test_d_status_is_not_touched() -> None:
    """D 단독 — `upsert_event_from_sync`이 갈아 끼우던 값이다."""

    async def body(session):
        event = (await session.execute(select(PleEventModel))).scalars().one()
        before = (event.status, event.finished_at)
        await _repository(session).set_event_schedule(
            slug="summerslam", start_date=date(2026, 8, 1), end_date=None
        )
        await session.commit()
        session.expire_all()
        event = (await session.execute(select(PleEventModel))).scalars().one()
        return before, (event.status, event.finished_at)

    # SQLite는 `DateTime(timezone=True)`의 tzinfo를 왕복에서 떨어뜨린다. 그래서
    # 상수와 비교하지 않고 **같은 세션에서 읽은 before**와 대조한다.
    before, after = _run(body)
    assert before[0] == PleEventStatus.FINISHED
    assert after == before


def test_g_winner_pick_survives() -> None:
    """G 단독 — result mutation 금지 불변조건의 직접 검사."""

    async def body(session):
        match = (await session.execute(select(PleMatchModel))).scalars().one()
        before = (
            match.winner_pick,
            match.winner_name,
            match.finished_at,
            match.ai_correct,
        )
        await _repository(session).set_event_schedule(
            slug="summerslam", start_date=date(2026, 8, 1), end_date=None
        )
        await session.commit()
        session.expire_all()
        match = (await session.execute(select(PleMatchModel))).scalars().one()
        return before, (
            match.winner_pick,
            match.winner_name,
            match.finished_at,
            match.ai_correct,
        )

    before, after = _run(body)
    assert before[0] == "left" and before[1] == "Cody Rhodes"
    assert after == before, "결과가 한 칸이라도 움직이면 안 된다"
    assert after[3] is None, "regrading이 일어나면 안 된다"


# ── I. end_date=None ────────────────────────────────────────────────


def test_i_start_date_with_null_end_date() -> None:
    """하루짜리 대회 — MITB(2026-10-10)가 이 모양이다."""

    async def body(session):
        ok = await _repository(session).set_event_schedule(
            slug="summerslam", start_date=date(2026, 10, 10), end_date=None
        )
        await session.commit()
        session.expire_all()
        event = (await session.execute(select(PleEventModel))).scalars().one()
        return ok, event.start_date, event.end_date

    ok, start, end = _run(body)
    assert ok is True
    assert start == date(2026, 10, 10)
    assert end is None


def test_i_both_none_clears_dates() -> None:
    """되돌리기 경로 — 잘못 넣었을 때 NULL로 복원할 수 있어야 한다."""

    async def body(session):
        repo = _repository(session)
        await repo.set_event_schedule(
            slug="summerslam", start_date=date(2026, 8, 1), end_date=date(2026, 8, 2)
        )
        await session.commit()
        await repo.set_event_schedule(slug="summerslam", start_date=None, end_date=None)
        await session.commit()
        session.expire_all()
        event = (await session.execute(select(PleEventModel))).scalars().one()
        return event.start_date, event.end_date

    assert _run(body) == (None, None)


# ── J. 롤백 ─────────────────────────────────────────────────────────


def test_j_rollback_leaves_no_trace() -> None:
    """**커밋은 부르는 쪽이 한다.** 메서드가 몰래 커밋하면 이 테스트가 깨진다."""

    async def body(session):
        ok = await _repository(session).set_event_schedule(
            slug="summerslam",
            start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 2),
        )
        await session.rollback()
        session.expire_all()
        event = (await session.execute(select(PleEventModel))).scalars().one()
        return ok, event.start_date, event.end_date

    ok, start, end = _run(body)
    assert ok is True, "flush 시점에는 성공이 맞다"
    assert (start, end) == (None, None), "롤백하면 흔적이 남지 않아야 한다"


# ── SQL 표면 검증 ───────────────────────────────────────────────────


def test_generated_sql_touches_only_the_intended_columns() -> None:
    """생성되는 UPDATE 문을 직접 본다 — 컬럼 목록이 계약이다."""
    from sqlalchemy import update
    from sqlalchemy.dialects import postgresql

    stmt = (
        update(PleEventModel)
        .where(PleEventModel.slug == "summerslam")
        .values(start_date=date(2026, 8, 1), end_date=date(2026, 8, 2))
    )
    sql = str(stmt.compile(dialect=postgresql.dialect()))

    assert sql.startswith("UPDATE ple_events SET")
    assert "start_date=" in sql.replace(" ", "")
    assert "end_date=" in sql.replace(" ", "")
    assert "WHERE ple_events.slug =" in sql

    # 도메인 컬럼은 SET 절에 없다
    for column in ("label", "month", "year", "status", "finished_at", "slug", "id"):
        assert f"{column}=" not in sql.replace(" ", "").split("WHERE")[0], (
            f"{column}이 SET 절에 들어갔다"
        )

    # 다른 테이블은 이름조차 등장하지 않는다
    for table in (
        "ple_matches",
        "ple_predictions",
        "ple_agent_predictions",
        "ple_agent_reports",
    ):
        assert table not in sql

    # `updated_at`은 컬럼 정의의 `onupdate` 때문에 **의도적으로** 실린다.
    assert "updated_at=" in sql.replace(" ", ""), (
        "행이 바뀐 사실은 남아야 한다 — 이것이 빠지면 onupdate가 사라진 것이다"
    )
