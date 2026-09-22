"""날짜 지난 대회 status 전이 스크립트 (Phase 3-13 Stage 8).

이 파일이 붙드는 것은 셋이다:

1. 날짜가 지난 `upcoming` 행이 `finished`가 된다.
2. 그러면서 **`finished_at`이 `NULL`로 남고 경기·예측이 하나도 바뀌지 않는다** —
   `mark_event_finished`(다른 경로)가 건드리는 것들이 그대로인지 본다.
3. 날짜를 모르는 행(`bad-blood`·`king-queen-of-the-ring`)은 **보류**다.

`today`를 주입받으므로 시간이 흘러도 이 테스트는 같은 것을 본다.

SQLite 인메모리에서 **실제 쿼리를 돌린다** — production DB를 쓰지 않는다.

실행:

    cd fastapi
    PYTHONUTF8=1 PYTHONPATH=apps uv run pytest apps/kayfabe/tests/scripts -q
"""

from __future__ import annotations

import asyncio
import importlib.util
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from types import ModuleType

import pytest
from core.entities.user_model import UserModel
from core.matrix.grid_oracle_database_manager import Base
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

# `outbound.mappers.__init__` ↔ `inbound.api` 순환 회피 — main.py와 같은 순서다.
import kayfabe.adapter.inbound.api.v1.ple_events_router  # noqa: F401,E402
from kayfabe.adapter.outbound.orm.agent_prediction_orm import (  # noqa: E402
    AgentPredictionModel,
    AgentReportModel,
    PredictionRetrievalModel,
)
from kayfabe.adapter.outbound.orm.ple_orm import (  # noqa: E402
    PleEventModel,
    PleEventStatus,
    PleMatchModel,
    PleMatchStatus,
    PlePredictionModel,
)
from kayfabe.adapter.outbound.pg.ple_events_pg_repository import (  # noqa: E402
    PleEventsPgRepository,
)

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "close_past_events.py"

_TABLES = [
    # `ple_predictions.user_id`가 `users`를 참조한다 — 빠뜨리면 FK 해석이 깨진다.
    UserModel.__table__,
    PleEventModel.__table__,
    PleMatchModel.__table__,
    PlePredictionModel.__table__,
    AgentPredictionModel.__table__,
    AgentReportModel.__table__,
    PredictionRetrievalModel.__table__,
]

_FINISHED_AT = datetime(2026, 8, 4, 6, 57, 58, tzinfo=UTC)
_GENERATED_AT = datetime(2026, 8, 5, 5, 39, 50, tzinfo=UTC)

#: 시드의 기준일. `worlds-collide`(9.26)는 아직 안 지났고 `heatwave`(8.30)는 지났다.
_TODAY = date(2026, 9, 22)

#: 날짜가 지났는데 `upcoming`으로 남아 있던 대회 — 이 스크립트를 만든 이유다.
_DRIFTED = "heatwave"
#: 아직 안 지난 대회.
_UPCOMING = "worlds-collide"
#: 날짜를 영영 모르는 대회 (2026에 열리지 않는다).
_UNDATED = "bad-blood"
#: 결과까지 기록된 대회.
_DONE = "summerslam"


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("_close_past_events_script", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # `@dataclass`가 어노테이션을 풀 때 `sys.modules[cls.__module__]`를 본다.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def script() -> ModuleType:
    return _load_script()


def _change(script: ModuleType, **kwargs) -> object:
    """기본값은 "지났고 upcoming" — 각 테스트가 한 칸씩만 바꾼다."""
    return script.StatusChange(
        **{
            "slug": _DRIFTED,
            "status": PleEventStatus.UPCOMING,
            "start_date": date(2026, 8, 30),
            "end_date": None,
            "today": _TODAY,
            **kwargs,
        }
    )


async def _seed() -> tuple[AsyncSession, object]:
    """production을 닮은 최소 상태: 드리프트 1 · 미래 1 · 날짜 미상 1 · 완료 1."""
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
            slug=_DONE,
            label="SummerSlam",
            month=8,
            year=2026,
            status=PleEventStatus.FINISHED,
            finished_at=_FINISHED_AT,
            start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 2),
        )
    )
    session.add(
        PleEventModel(
            id=2,
            slug=_DRIFTED,
            label="NXT Heatwave",
            month=8,
            year=2026,
            status=PleEventStatus.UPCOMING,
            start_date=date(2026, 8, 30),
        )
    )
    session.add(
        PleEventModel(
            id=3,
            slug=_UPCOMING,
            label="Worlds Collide",
            month=9,
            year=2026,
            status=PleEventStatus.UPCOMING,
            start_date=date(2026, 9, 26),
        )
    )
    session.add(
        PleEventModel(
            id=4,
            slug=_UNDATED,
            label="Bad Blood",
            month=10,
            year=2026,
            status=PleEventStatus.UPCOMING,
        )
    )
    session.add(
        PleMatchModel(
            id=10,
            event_id=2,
            match_key="hw26-main",
            title="NXT Championship",
            format="singles",
            card_variant="sideA",
            card_json='{"format": "singles"}',
            sort_order=0,
            status=PleMatchStatus.SCHEDULED,
            # 결과가 없는데 `winner_pick`만 있는 상태 — `mark_event_finished`라면
            # 이 경기를 `FINISHED`로 넘겼을 자리다.
            winner_pick="left",
            point_value=3,
        )
    )
    session.add(
        PlePredictionModel(id=100, match_id=10, client_id="client-1", pick="left")
    )
    session.add(
        AgentPredictionModel(
            id=200,
            event_id=2,
            match_key="hw26-main",
            pick="left",
            pick_name="Oba Femi",
            win_probability=0.7,
            confidence=0.5,
            rationale="근거",
            source="agents",
            generated_at=_GENERATED_AT,
        )
    )
    await session.commit()
    return session, engine


async def _untouched_snapshot(session: AsyncSession) -> dict:
    """`status` 말고 바뀌면 안 되는 것 전부. `updated_at`은 장부 칸이라 뺀다."""
    event = await session.scalar(
        select(PleEventModel).where(PleEventModel.slug == _DRIFTED)
    )
    match = (await session.execute(select(PleMatchModel))).scalars().one()
    prediction = (await session.execute(select(PlePredictionModel))).scalars().one()
    agent = (await session.execute(select(AgentPredictionModel))).scalars().one()
    return {
        "event_other": (
            event.id,
            event.slug,
            event.label,
            event.month,
            event.year,
            event.start_date,
            event.end_date,
            event.finished_at,
        ),
        "match": (
            match.id,
            match.event_id,
            match.match_key,
            match.title,
            match.card_json,
            match.status,
            match.winner_pick,
            match.winner_name,
            match.finished_at,
            match.point_value,
        ),
        "prediction": (prediction.id, prediction.match_id, prediction.pick),
        "agent": (agent.id, agent.event_id, agent.match_key, agent.pick),
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


class TestNeedsWrite:
    """무엇을 쓸지 고르는 규칙 — DB 없이 판정된다."""

    def test_past_upcoming_is_written(self, script: ModuleType) -> None:
        assert _change(script).needs_write is True

    def test_future_event_is_left_alone(self, script: ModuleType) -> None:
        assert _change(script, start_date=date(2026, 9, 26)).needs_write is False

    def test_today_is_not_past(self, script: ModuleType) -> None:
        """당일에는 넘기지 않는다 — 대회는 각자의 현지 시각에 열린다."""
        change = _change(script, start_date=_TODAY)

        assert change.is_past is False
        assert change.needs_write is False

    def test_yesterday_is_past(self, script: ModuleType) -> None:
        """경계 바로 아래. `<` 판정이 `<=`로 미끄러지면 여기가 깨진다."""
        change = _change(script, start_date=date(2026, 9, 21))

        assert change.is_past is True
        assert change.needs_write is True

    def test_end_date_decides_for_multi_day_events(self, script: ModuleType) -> None:
        """이틀짜리 대회는 둘째 날이 마지막 날이다."""
        change = _change(
            script, start_date=date(2026, 9, 21), end_date=date(2026, 9, 23)
        )

        assert change.last_day == date(2026, 9, 23)
        assert change.needs_write is False

    def test_finished_is_never_reverted(self, script: ModuleType) -> None:
        """한 방향으로만 흐른다."""
        change = _change(script, status=PleEventStatus.FINISHED)

        assert change.is_past is True
        assert change.needs_write is False

    def test_live_past_event_is_also_closed(self, script: ModuleType) -> None:
        """`live`도 "아직 안 끝났다"는 주장이고, 날짜가 지났으면 거짓이다."""
        assert _change(script, status=PleEventStatus.LIVE).needs_write is True

    def test_undated_event_is_held_not_written(self, script: ModuleType) -> None:
        """날짜를 모르면 통과가 아니라 보류다 — bad-blood가 영구히 이 자리다."""
        change = _change(script, start_date=None)

        assert change.held is True
        assert change.is_past is False
        assert change.needs_write is False


class TestExitCode:
    def test_exit_codes_are_distinct_and_nonzero(self, script: ModuleType) -> None:
        codes = {script.EXIT_USAGE, script.EXIT_NO_DATABASE}

        assert len(codes) == 2
        assert 0 not in codes


class TestCollectChanges:
    def test_every_row_is_considered(self, script: ModuleType) -> None:
        """카탈로그로 거르지 않는다 — 화면에서 감춘 대회의 상태도 참이어야 한다."""
        changes = _run(lambda s: script.collect_changes(s, today=_TODAY))

        assert [change.slug for change in changes] == sorted(
            [_DONE, _DRIFTED, _UPCOMING, _UNDATED]
        )

    def test_only_the_drifted_row_needs_writing(self, script: ModuleType) -> None:
        changes = _run(lambda s: script.collect_changes(s, today=_TODAY))

        assert [c.slug for c in changes if c.needs_write] == [_DRIFTED]
        assert [c.slug for c in changes if c.held] == [_UNDATED]


class TestApplyChanges:
    def test_drifted_row_becomes_finished(self, script: ModuleType) -> None:
        async def body(session: AsyncSession) -> tuple:
            changes = await script.collect_changes(session, today=_TODAY)
            written = await script.apply_changes(
                PleEventsPgRepository(session), changes
            )
            await session.commit()
            session.expire_all()
            rows = {
                row.slug: row.status
                for row in (await session.scalars(select(PleEventModel))).all()
            }
            return written, rows

        written, rows = _run(body)

        assert written == 1
        assert rows[_DRIFTED] == PleEventStatus.FINISHED
        assert rows[_UPCOMING] == PleEventStatus.UPCOMING
        assert rows[_UNDATED] == PleEventStatus.UPCOMING
        assert rows[_DONE] == PleEventStatus.FINISHED

    def test_finished_at_stays_null(self, script: ModuleType) -> None:
        """**이 파일의 핵심.** `finished` + `finished_at IS NULL`이
        "끝났지만 결과 미기록"을 말한다. 시각을 지어내면 그 뜻이 사라진다."""

        async def body(session: AsyncSession) -> datetime | None:
            changes = await script.collect_changes(session, today=_TODAY)
            await script.apply_changes(PleEventsPgRepository(session), changes)
            await session.commit()
            session.expire_all()
            event = await session.scalar(
                select(PleEventModel).where(PleEventModel.slug == _DRIFTED)
            )
            return event.finished_at

        assert _run(body) is None

    def test_nothing_but_the_status_column_moves(self, script: ModuleType) -> None:
        """경기·사용자 예측·에이전트 예측이 그대로여야 한다.

        시드의 경기는 `winner_pick`이 있고 `scheduled`다 —
        `mark_event_finished`였다면 이것을 `finished`로 넘겼을 자리다.
        """

        async def body(session: AsyncSession) -> tuple[dict, dict]:
            before = await _untouched_snapshot(session)
            changes = await script.collect_changes(session, today=_TODAY)
            await script.apply_changes(PleEventsPgRepository(session), changes)
            await session.commit()
            session.expire_all()
            after = await _untouched_snapshot(session)
            return before, after

        before, after = _run(body)

        assert after == before

    def test_second_run_writes_nothing(self, script: ModuleType) -> None:
        """멱등 — 한 번 넘기고 나면 `needs_write`가 전부 꺼진다."""

        async def body(session: AsyncSession) -> int:
            first = await script.collect_changes(session, today=_TODAY)
            await script.apply_changes(PleEventsPgRepository(session), first)
            await session.commit()
            session.expire_all()
            second = await script.collect_changes(session, today=_TODAY)
            return await script.apply_changes(PleEventsPgRepository(session), second)

        assert _run(body) == 0

    def test_missing_row_raises_instead_of_passing(self, script: ModuleType) -> None:
        """`collect_changes`가 본 행이 사라졌으면 조용히 넘기지 않는다."""

        async def body(session: AsyncSession) -> None:
            changes = [_change(script, slug="does-not-exist")]
            with pytest.raises(RuntimeError, match="does-not-exist"):
                await script.apply_changes(PleEventsPgRepository(session), changes)

        _run(body)
