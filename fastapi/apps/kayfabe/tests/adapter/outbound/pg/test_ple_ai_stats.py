"""적중률 집계 테스트 — **에이전트 예측만 센다** (하네스 §13-Q4 결정).

예전 집계는 `ple_matches.ai_pick`(카드 동기화 때 배당으로 파생한 값)을 셌다. 그 기록과
멀티 에이전트 기록이 한 숫자로 섞이면 무엇의 적중률인지 말할 수 없다. 그래서 집계
대상을 `ple_agent_predictions`로 옮겼고, 이 파일이 그 계약을 고정한다.

**사후 재현 표본도 세지 않는다** (Phase 3-9). 이 쿼리가 홈 화면 KPI가 읽는 유일한
채점 경로인데, SQL에서 바로 집계해서 `ai_lab_integrity.is_scorable()`을 부를 자리가
없다. 그래서 같은 뜻이 파이썬과 SQL 두 곳에 적혀 있고, 아래 테스트들이 그 둘이
갈라지지 않게 붙든다.

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
    pid: int,
    *,
    key: str,
    pick: str,
    source: str = "agents",
    outcome_known_externally: bool | None = None,
) -> AgentPredictionModel:
    """기본값 `None` = **아무도 선언하지 않았다** — 기존 테스트가 지나는 길이다."""
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
        outcome_known_externally=outcome_known_externally,
        provenance_note="사후 재현 표본." if outcome_known_externally else None,
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


def test_ex_post_sample_is_excluded_even_with_a_result() -> None:
    """**이 파일에서 가장 중요한 테스트다** (Phase 3-9).

    사후 재현 표본은 결과가 들어와도 홈 KPI를 움직이지 않아야 한다. 이 조건이
    없으면 Bad Blood·King & Queen 7건의 결과를 넣는 순간 홈 화면만 AI LAB과
    다른 적중률을 말한다 — AI LAB은 같은 7건을 `ex_post`로 빼고 있는데도.

    ex-post 쪽을 **오답**으로 둔 이유는, 빠지지 않았을 때 값이 눈에 띄게
    틀어지게 하기 위해서다(2/2 → 1/2, 100% → 50%).
    """
    stats = _stats(
        [
            _match(1, key="a", winner="left"),
            _match(2, key="b", winner="right"),
            _prediction(10, key="a", pick="left"),
            _prediction(11, key="b", pick="left", outcome_known_externally=True),
        ]
    )

    assert stats.total_graded == 1
    assert stats.correct == 1
    assert stats.incorrect == 0
    assert stats.accuracy_percent == 100.0
    assert [r.match_key for r in stats.recent] == ["a"]


def test_undeclared_none_is_still_graded() -> None:
    """**`NULL`은 "모른다"가 아니라 "선언되지 않았다"이다.**

    운영의 기존 12건이 전부 이 자리에 있다. SQL을 `== False`로 썼다면 여기서
    깨진다 — 아무도 선언한 적 없는 표본이 통째로 채점에서 빠진다.
    """
    stats = _stats(
        [
            _match(1, key="a", winner="left"),
            _prediction(10, key="a", pick="left", outcome_known_externally=None),
        ]
    )

    assert stats.total_graded == 1
    assert stats.correct == 1
    assert [r.match_key for r in stats.recent] == ["a"]


def test_declared_false_is_still_graded() -> None:
    """`False`는 "결과가 밖에 알려지지 않았다"고 **명시한** 것이다 — 채점한다.

    `None`과 뜻은 다르지만 채점 여부는 같다. 셋 중 `True` 하나만 빠진다.
    """
    stats = _stats(
        [
            _match(1, key="a", winner="left"),
            _prediction(10, key="a", pick="left", outcome_known_externally=False),
        ]
    )

    assert stats.total_graded == 1
    assert stats.correct == 1
    assert [r.match_key for r in stats.recent] == ["a"]


def test_recent_and_aggregate_share_one_population() -> None:
    """`recent[]`와 집계가 **같은 서브쿼리**에서 나온다는 계약.

    둘이 갈라지면 화면이 "12건 채점"이라 적고 목록에는 19줄을 그리게 된다.
    셋을 섞어 두고 길이와 합계가 함께 움직이는지 본다.
    """
    stats = _stats(
        [
            _match(1, key="a", winner="left"),
            _match(2, key="b", winner="left"),
            _match(3, key="c", winner="left"),
            _match(4, key="d", winner="left"),
            _prediction(10, key="a", pick="left"),
            _prediction(11, key="b", pick="left", outcome_known_externally=False),
            _prediction(12, key="c", pick="left", outcome_known_externally=True),
            _prediction(13, key="d", pick="left", source="bookmaker_fallback"),
        ]
    )

    assert stats.total_graded == 2
    assert len(stats.recent) == stats.total_graded
    assert [r.match_key for r in stats.recent] == ["a", "b"]
    assert stats.correct + stats.incorrect == stats.total_graded


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
