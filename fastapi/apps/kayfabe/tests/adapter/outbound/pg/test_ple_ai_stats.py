"""적중률 집계 테스트 — **에이전트 예측만 센다** (하네스 §13-Q4 결정).

예전 집계는 `ple_matches.ai_pick`(카드 동기화 때 배당으로 파생한 값)을 셌다. 그 기록과
멀티 에이전트 기록이 한 숫자로 섞이면 무엇의 적중률인지 말할 수 없다. 그래서 집계
대상을 `ple_agent_predictions`로 옮겼고, 이 파일이 그 계약을 고정한다.

SQLite 인메모리에서 실제 쿼리를 돌린다 — 이 경로에는 pgvector 타입이 없다.

실행:

    cd fastapi
    PYTHONUTF8=1 PYTHONPATH=apps uv run pytest apps/kayfabe/tests -q
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from datetime import UTC, datetime

from core.matrix.grid_oracle_database_manager import Base
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from kayfabe.adapter.outbound.orm.agent_prediction_orm import (
    AgentPredictionModel,
    AgentReportModel,
)
from kayfabe.adapter.outbound.orm.ple_orm import (
    PleEventModel,
    PleMatchModel,
    PleMatchStatus,
)

_TABLES = [
    PleEventModel.__table__,
    PleMatchModel.__table__,
    AgentPredictionModel.__table__,
    AgentReportModel.__table__,
]

_NOW = datetime(2026, 8, 5, tzinfo=UTC)


def _match(
    mid: int, *, key: str, winner: str | None, ai_pick: str | None = None
) -> PleMatchModel:
    """`ai_pick`은 규칙 기반 시절의 잔재다 — 집계가 이 값을 보지 않아야 한다."""
    return PleMatchModel(
        id=mid,
        event_id=1,
        match_key=key,
        title=f"Match {mid}",
        format="singles",
        card_json="{}",
        status=PleMatchStatus.FINISHED if winner else PleMatchStatus.SCHEDULED,
        winner_pick=winner,
        winner_name="승자" if winner else None,
        sort_order=mid,
        ai_pick=ai_pick,
        ai_pick_name="옛 예측" if ai_pick else None,
        ai_correct=True if ai_pick else None,
    )


def _prediction(
    pid: int, *, key: str, pick: str, source: str = "agents"
) -> AgentPredictionModel:
    return AgentPredictionModel(
        id=pid,
        event_id=1,
        match_key=key,
        pick=pick,
        pick_name=f"{pick} 선수",
        win_probability=0.7,
        confidence=0.5,
        rationale="근거",
        source=source,
        generated_at=_NOW,
    )


async def _seed(objects: Sequence[object]) -> AsyncSession:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(lambda c: Base.metadata.create_all(c, tables=_TABLES))

    factory = async_sessionmaker(engine, expire_on_commit=False)
    session = factory()
    session.add(PleEventModel(id=1, slug="summerslam", label="SummerSlam", year=2026))
    session.add_all(list(objects))
    await session.commit()
    return session


def _stats(objects: Sequence[object]):
    # 지연 임포트: `outbound.mappers.__init__`가 `inbound.api`를 거쳐 다시 자신을
    # 부르는 기존 순환이 있어, 이 모듈을 맨 먼저 임포트하면 수집 단계에서 깨진다.
    # (운영에서는 main.py가 라우터를 먼저 임포트해 순서가 맞는다.)
    from kayfabe.adapter.outbound.pg.ple_events_pg_repository import (
        PleEventsPgRepository,
    )

    async def run():
        session = await _seed(objects)
        try:
            return await PleEventsPgRepository(session).get_ai_stats()
        finally:
            await session.close()

    return asyncio.run(run())


def test_counts_only_agent_predictions() -> None:
    """규칙 기반 시절 기록(`ai_pick`)은 세지 않는다 — 예측 행이 없으면 없는 것이다."""
    stats = _stats(
        [
            _match(1, key="a", winner="left", ai_pick="left"),
            _match(2, key="b", winner="right", ai_pick="left"),
            _prediction(10, key="a", pick="left"),
        ]
    )

    assert stats.total_graded == 1
    assert stats.correct == 1
    assert stats.accuracy_percent == 100.0
    assert [r.match_key for r in stats.recent] == ["a"]
    assert stats.recent[0].ai_pick_name == "left 선수"


def test_wrong_pick_counts_as_incorrect() -> None:
    stats = _stats(
        [
            _match(1, key="a", winner="left"),
            _match(2, key="b", winner="right"),
            _prediction(10, key="a", pick="left"),
            _prediction(11, key="b", pick="left"),
        ]
    )

    assert (stats.total_graded, stats.correct, stats.incorrect) == (2, 1, 1)
    assert stats.accuracy_percent == 50.0
    assert [r.correct for r in stats.recent] == [True, False]


def test_bookmaker_fallback_is_excluded() -> None:
    """폴백은 배당으로 만든 예측이다 — 지우기로 한 그 숫자가 다시 섞이면 안 된다."""
    stats = _stats(
        [
            _match(1, key="a", winner="left"),
            _match(2, key="b", winner="left"),
            _prediction(10, key="a", pick="left"),
            _prediction(11, key="b", pick="left", source="bookmaker_fallback"),
        ]
    )

    assert stats.total_graded == 1
    assert [r.match_key for r in stats.recent] == ["a"]


def test_unfinished_match_is_not_graded() -> None:
    """결과가 안 나온 경기는 맞았다고도 틀렸다고도 할 수 없다."""
    stats = _stats(
        [
            _match(1, key="a", winner=None),
            _prediction(10, key="a", pick="left"),
        ]
    )

    assert stats.total_graded == 0
    assert stats.accuracy_percent is None
    assert stats.recent == []


def test_no_predictions_at_all() -> None:
    stats = _stats([_match(1, key="a", winner="left", ai_pick="left")])

    assert (stats.total_graded, stats.correct, stats.incorrect) == (0, 0, 0)
    assert stats.accuracy_percent is None
