"""카탈로그 날짜 반영 스크립트 (Phase 3-13 Stage 3-B).

**3-A는 문만 냈고 부르는 곳이 없었다.** 그래서 이 파일이 붙드는 것은 둘이다:

1. 카탈로그 값이 실제로 `ple_events`의 날짜 두 칸에 들어간다.
2. 그러면서 **경기·사용자 예측·에이전트 예측이 하나도 바뀌지 않는다** — 날짜를
   쓰는 다른 경로(`upsert_event_from_sync`)가 지우는 것들이 그대로 남는지 본다.

스크립트는 `sys.path`를 직접 만지는 standalone이라 패키지로 import되지 않는다.
파일 경로로 읽어 온다 — 실제로 실행되는 그 파일을 검사하기 위해서다.

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
from kayfabe.adapter.outbound.catalog.ple_event_schedule_catalog import (  # noqa: E402
    PLE_EVENT_SCHEDULE,
)
from kayfabe.adapter.outbound.orm.agent_prediction_orm import (  # noqa: E402
    AgentPredictionModel,
    AgentReportModel,
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

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "apply_event_schedule.py"

_TABLES = [
    # `ple_predictions.user_id`가 `users`를 참조한다 — 빠뜨리면 FK 해석이 깨진다.
    UserModel.__table__,
    PleEventModel.__table__,
    PleMatchModel.__table__,
    PlePredictionModel.__table__,
    AgentPredictionModel.__table__,
    # `AgentPredictionModel.reports`가 selectin으로 딸려 온다 — 빠뜨리면 재조회가 깨진다.
    AgentReportModel.__table__,
]

_FINISHED_AT = datetime(2026, 8, 4, 6, 57, 58, tzinfo=UTC)
_GENERATED_AT = datetime(2026, 8, 5, 5, 39, 50, tzinfo=UTC)

#: 카탈로그가 확인한 값. 스크립트가 이 값을 그대로 넣는지 본다.
_SUMMERSLAM = (date(2026, 8, 1), date(2026, 8, 2))
#: 일정 미정이라 카탈로그에 없는 대회.
_UNTRACKED_SLUG = "bad-blood"


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("_apply_schedule_script", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # `@dataclass`가 어노테이션을 풀 때 `sys.modules[cls.__module__]`를 본다.
    # 등록하지 않고 exec하면 `ScheduleChange` 정의에서 깨진다.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def script() -> ModuleType:
    return _load_script()


async def _seed(
    *,
    summerslam_dates: tuple[date | None, date | None] = (None, None),
    untracked_dates: tuple[date | None, date | None] = (None, None),
) -> tuple[AsyncSession, object]:
    """production을 닮은 최소 상태: 날짜가 빈 대회 + 경기 + 예측들."""
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
            start_date=summerslam_dates[0],
            end_date=summerslam_dates[1],
        )
    )
    session.add(
        PleEventModel(
            id=2,
            slug=_UNTRACKED_SLUG,
            label="Bad Blood",
            month=10,
            year=2026,
            status=PleEventStatus.UPCOMING,
            start_date=untracked_dates[0],
            end_date=untracked_dates[1],
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
    await session.commit()
    return session, engine


async def _untouched_snapshot(session: AsyncSession) -> dict:
    """날짜 말고 바뀌면 안 되는 것 전부. `updated_at`은 장부 칸이라 뺀다."""
    event = await session.scalar(
        select(PleEventModel).where(PleEventModel.slug == "summerslam")
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
            event.status,
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


def _run(body, **seed_kwargs):
    async def go():
        session, engine = await _seed(**seed_kwargs)
        try:
            return await body(session)
        finally:
            await session.close()
            await engine.dispose()

    return asyncio.run(go())


class TestNeedsWrite:
    """무엇을 쓸지 고르는 규칙 — DB 없이 판정된다."""

    def test_same_value_is_not_written(self, script: ModuleType) -> None:
        """무변경 쓰기는 `updated_at`만 거짓으로 밀어 올린다."""
        change = script.ScheduleChange(
            slug="summerslam",
            found=True,
            current=_SUMMERSLAM,
            catalog=_SUMMERSLAM,
        )

        assert change.needs_write is False

    def test_null_to_value_is_written(self, script: ModuleType) -> None:
        change = script.ScheduleChange(
            slug="summerslam",
            found=True,
            current=(None, None),
            catalog=_SUMMERSLAM,
        )

        assert change.needs_write is True

    def test_end_date_alone_differing_is_written(self, script: ModuleType) -> None:
        """이틀짜리 대회의 둘째 날이 빠져 있던 경우."""
        change = script.ScheduleChange(
            slug="summerslam",
            found=True,
            current=(date(2026, 8, 1), None),
            catalog=_SUMMERSLAM,
        )

        assert change.needs_write is True

    def test_missing_row_is_never_written(self, script: ModuleType) -> None:
        """**행을 만들지 않는다** — Survivor Series를 만들지 않기로 한 결정이 여기 걸린다."""
        change = script.ScheduleChange(
            slug="survivor-series",
            found=False,
            current=(None, None),
            catalog=(date(2026, 11, 28), None),
        )

        assert change.needs_write is False


class TestExitCode:
    def test_all_present_succeeds(self, script: ModuleType) -> None:
        changes = [
            script.ScheduleChange(
                slug="summerslam",
                found=True,
                current=(None, None),
                catalog=_SUMMERSLAM,
            )
        ]

        assert script.exit_code_for(changes) == 0

    def test_missing_event_is_reported(self, script: ModuleType) -> None:
        """쓰기가 성공해도 카탈로그와 DB가 어긋난 사실은 따로 알린다."""
        changes = [
            script.ScheduleChange(
                slug="summerslam",
                found=True,
                current=(None, None),
                catalog=_SUMMERSLAM,
            ),
            script.ScheduleChange(
                slug="survivor-series",
                found=False,
                current=(None, None),
                catalog=(date(2026, 11, 28), None),
            ),
        ]

        assert script.exit_code_for(changes) == script.EXIT_MISSING_EVENT
        assert script.EXIT_MISSING_EVENT != 0

    def test_exit_codes_are_distinct(self, script: ModuleType) -> None:
        codes = {
            script.EXIT_MISSING_EVENT,
            script.EXIT_USAGE,
            script.EXIT_NO_DATABASE,
        }

        assert len(codes) == 3
        assert 0 not in codes


class TestCollectChanges:
    def test_only_catalog_slugs_are_considered(self, script: ModuleType) -> None:
        """카탈로그 밖 대회는 아예 후보에 오르지 않는다 — `(None, None)`을 쓸 일이 없다."""
        changes = _run(script.collect_changes)

        assert [change.slug for change in changes] == sorted(PLE_EVENT_SCHEDULE)
        assert _UNTRACKED_SLUG not in {change.slug for change in changes}

    def test_seeded_event_is_found_with_null_dates(self, script: ModuleType) -> None:
        changes = _run(script.collect_changes)
        summerslam = next(c for c in changes if c.slug == "summerslam")

        assert summerslam.found is True
        assert summerslam.current == (None, None)
        assert summerslam.catalog == _SUMMERSLAM

    def test_unsynced_events_are_flagged_not_created(self, script: ModuleType) -> None:
        """이 시드에는 summerslam 하나뿐이라 나머지 카탈로그 대회는 전부 `found=False`다."""
        changes = _run(script.collect_changes)
        missing = [change.slug for change in changes if not change.found]

        assert "summerslam" not in missing
        assert missing, "시드에 없는 카탈로그 대회가 있어야 이 판정이 의미가 있다"
        assert script.exit_code_for(changes) == script.EXIT_MISSING_EVENT


class TestUntrackedDrift:
    def test_untracked_event_with_dates_is_reported(self, script: ModuleType) -> None:
        """카탈로그가 모르는 날짜는 지우지 않고 사람에게 보인다."""
        drift = _run(
            script.untracked_dated_events,
            untracked_dates=(date(2026, 10, 3), None),
        )

        assert drift == [(_UNTRACKED_SLUG, date(2026, 10, 3), None)]

    def test_untracked_event_without_dates_is_quiet(self, script: ModuleType) -> None:
        drift = _run(script.untracked_dated_events)

        assert drift == []


class TestApplyChanges:
    def test_catalog_dates_land_in_the_row(self, script: ModuleType) -> None:
        async def body(session: AsyncSession) -> tuple:
            changes = await script.collect_changes(session)
            written = await script.apply_changes(
                PleEventsPgRepository(session), changes
            )
            await session.commit()
            event = await session.scalar(
                select(PleEventModel).where(PleEventModel.slug == "summerslam")
            )
            return written, (event.start_date, event.end_date)

        written, dates = _run(body)

        assert written == 1, "시드에 있는 카탈로그 대회는 summerslam 하나뿐이다"
        assert dates == _SUMMERSLAM

    def test_nothing_but_the_two_columns_moves(self, script: ModuleType) -> None:
        """**이 파일의 핵심.** 사용자 예측이 날아가지 않는지가 3-A를 만든 이유다."""

        async def body(session: AsyncSession) -> tuple[dict, dict]:
            before = await _untouched_snapshot(session)
            changes = await script.collect_changes(session)
            await script.apply_changes(PleEventsPgRepository(session), changes)
            await session.commit()
            session.expire_all()
            after = await _untouched_snapshot(session)
            return before, after

        before, after = _run(body)

        assert after == before

    def test_untracked_event_dates_survive(self, script: ModuleType) -> None:
        """카탈로그 밖 대회의 날짜를 `NULL`로 밀어 버리지 않는다."""

        async def body(session: AsyncSession) -> tuple:
            changes = await script.collect_changes(session)
            await script.apply_changes(PleEventsPgRepository(session), changes)
            await session.commit()
            session.expire_all()
            event = await session.scalar(
                select(PleEventModel).where(PleEventModel.slug == _UNTRACKED_SLUG)
            )
            return event.start_date, event.end_date

        assert _run(body, untracked_dates=(date(2026, 10, 3), None)) == (
            date(2026, 10, 3),
            None,
        )

    def test_second_run_writes_nothing(self, script: ModuleType) -> None:
        """멱등 — 값이 같아지면 `needs_write`가 전부 꺼진다."""

        async def body(session: AsyncSession) -> int:
            first = await script.collect_changes(session)
            await script.apply_changes(PleEventsPgRepository(session), first)
            await session.commit()
            session.expire_all()
            second = await script.collect_changes(session)
            return await script.apply_changes(PleEventsPgRepository(session), second)

        assert _run(body) == 0

    def test_already_correct_row_is_left_alone(self, script: ModuleType) -> None:
        """이미 카탈로그와 같으면 한 건도 쓰지 않는다."""

        async def body(session: AsyncSession) -> int:
            changes = await script.collect_changes(session)
            return await script.apply_changes(PleEventsPgRepository(session), changes)

        assert _run(body, summerslam_dates=_SUMMERSLAM) == 0
