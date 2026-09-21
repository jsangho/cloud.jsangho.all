"""검색 기록 저장 경로 (Phase 3-13 Stage 4).

이 파일이 붙드는 주장은 하나다 — **기록은 코퍼스보다 오래 살아야 한다.**

`ple_agent_reports.sources`에 남는 URL로는 "무엇을 읽었는가"에 답할 수 없다. 위키
문서는 경기 전후로 계속 고쳐지므로 같은 주소라도 개정본이 다르면 다른 글이고, 판정을
가르는 것이 바로 그 차이다. 그래서 그때 읽은 개정본을 예측에 붙여 둔다.

그런데 재수집은 그 URL의 옛 청크를 통째로 DELETE한다(`replace_document_chunks`).
청크에 FK를 걸면 코퍼스를 다시 모으는 순간 기록이 가리키는 행이 사라진다 — 증거가
필요한 바로 그때 증거가 없어진다. 그래서 값을 베껴 두고, 청크 테이블을 **참조하지
않는다**는 것을 스키마에서 확인한다.

반대로 예측에는 묶여 있어야 한다. 기록은 그 생성에 속하므로 재생성이 옛 기록을
데려가지 않으면 "무엇을 읽고 만든 예측인가"가 거짓이 된다.

SQLite 인메모리에서 **실제 쿼리를 돌린다** — production DB를 쓰지 않는다.

실행:

    cd fastapi
    PYTHONUTF8=1 PYTHONPATH=apps uv run pytest \
        apps/kayfabe/tests/adapter/outbound/pg/test_prediction_retrievals.py -q
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from core.matrix.grid_oracle_database_manager import Base
from sqlalchemy import delete, event, select
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
)
from kayfabe.adapter.outbound.pg.agent_prediction_pg_repository import (  # noqa: E402
    AgentPredictionPgRepository,
)
from kayfabe.domain.entities.agent_prediction import (  # noqa: E402
    AgentKind,
    AgentPrediction,
    AgentReport,
    KnowledgeRetrieval,
    PredictionSource,
)

_TABLES = [
    PleEventModel.__table__,
    AgentPredictionModel.__table__,
    AgentReportModel.__table__,
    PredictionRetrievalModel.__table__,
]

_GENERATED_AT = datetime(2026, 8, 5, 5, 39, 50, tzinfo=UTC)
_REVISED_AT = datetime(2026, 8, 5, 3, 7, 53, tzinfo=UTC)
_SUMMERSLAM_URL = "https://en.wikipedia.org/wiki/SummerSlam_(2026)"


def _retrieval(rank: int, *, chunk_id: int, url: str = _SUMMERSLAM_URL):
    return KnowledgeRetrieval(
        rank=rank,
        chunk_id=chunk_id,
        source_url=url,
        content_hash=str(chunk_id) * 8,
        source_revision_id=f"136777{chunk_id}",
        source_revised_at=_REVISED_AT,
        published_at=None,
        distance=0.1 * rank,
    )


def _prediction(*, retrievals: tuple[KnowledgeRetrieval, ...]) -> AgentPrediction:
    return AgentPrediction(
        event_slug="summerslam",
        match_key="ss26-n1-undisputed",
        pick="left",
        pick_name="Cody Rhodes",
        win_probability=0.7,
        confidence=0.5,
        rationale="근거",
        source=PredictionSource.AGENTS,
        generated_at=_GENERATED_AT,
        reports=(
            AgentReport(
                agent=AgentKind.STORYLINE,
                pick="left",
                weight=0.8,
                summary="명분이 챔피언 쪽에 있다.",
                sources=(_SUMMERSLAM_URL,),
            ),
        ),
        retrievals=retrievals,
    )


async def _seed() -> tuple[AsyncSession, object]:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _enforce_foreign_keys(dbapi_connection, _record) -> None:  # noqa: ANN001
        """**SQLite는 기본적으로 FK를 강제하지 않는다.**

        켜지 않으면 `ON DELETE CASCADE`가 돌지 않아, 예측을 지워도 기록이 남고
        재생성이 UNIQUE에 걸린다 — 운영(Postgres)에서는 일어나지 않는 일이다.
        여기서 확인하려는 것이 바로 그 캐스케이드라 끄고 테스트하면 의미가 없다.
        """
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

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
        )
    )
    await session.commit()
    return session, engine


def _run(body):
    async def go():
        session, engine = await _seed()
        try:
            return await body(session)
        finally:
            await session.close()
            await engine.dispose()

    return asyncio.run(go())


def test_it_saves_what_was_read_in_reading_order() -> None:
    async def body(session: AsyncSession) -> None:
        repository = AgentPredictionPgRepository(session)
        await repository.save(
            _prediction(
                retrievals=(
                    _retrieval(1, chunk_id=11),
                    _retrieval(2, chunk_id=12, url="https://en.wikipedia.org/wiki/Oba"),
                )
            )
        )
        await session.commit()

        rows = (
            (
                await session.execute(
                    select(PredictionRetrievalModel).order_by(
                        PredictionRetrievalModel.rank
                    )
                )
            )
            .scalars()
            .all()
        )
        assert [row.rank for row in rows] == [1, 2]
        assert [row.chunk_id for row in rows] == [11, 12]
        assert rows[0].source_revision_id == "13677711"
        # **SQLite는 tzinfo를 저장하지 않는다** — 값이 같은지만 본다. 운영은
        # `timestamptz`라 UTC가 그대로 돌아온다(`test_the_read_path_returns_the_record`
        # 도 같은 이유로 엔티티 쪽에서는 비교하지 않는다).
        assert rows[0].source_revised_at.replace(tzinfo=UTC) == _REVISED_AT
        assert rows[0].distance == 0.1

    _run(body)


def test_a_prediction_that_read_nothing_writes_no_rows() -> None:
    """빈 기록은 빈 채로 둔다 — 0건짜리 행을 만들어 "읽었다"고 적지 않는다."""

    async def body(session: AsyncSession) -> None:
        await AgentPredictionPgRepository(session).save(_prediction(retrievals=()))
        await session.commit()

        rows = (await session.execute(select(PredictionRetrievalModel))).all()
        assert rows == []

    _run(body)


def test_regenerating_replaces_the_old_record() -> None:
    """재생성은 예측 행을 갈아 끼운다 — 옛 생성의 기록이 새 예측에 남으면 거짓이 된다."""

    async def body(session: AsyncSession) -> None:
        repository = AgentPredictionPgRepository(session)
        await repository.save(_prediction(retrievals=(_retrieval(1, chunk_id=11),)))
        await session.commit()
        # 재생성은 다른 요청이다 — 한 세션이 옛 행과 새 행을 동시에 들고 있지
        # 않도록 비운다. (SQLite는 지운 id를 재사용해서 식별자 맵이 겹친다.)
        session.expunge_all()

        await repository.save(
            _prediction(
                retrievals=(
                    _retrieval(1, chunk_id=99),
                    _retrieval(2, chunk_id=98),
                )
            )
        )
        await session.commit()

        rows = (
            (
                await session.execute(
                    select(PredictionRetrievalModel).order_by(
                        PredictionRetrievalModel.rank
                    )
                )
            )
            .scalars()
            .all()
        )
        assert [row.chunk_id for row in rows] == [99, 98]

    _run(body)


def test_the_record_does_not_reference_the_chunk_table() -> None:
    """**이 검사가 스냅샷 설계의 이유다.**

    재수집은 그 URL의 옛 청크를 통째로 DELETE한다(`replace_document_chunks`).
    `chunk_id`에 FK가 걸리는 순간 그 DELETE가 기록까지 끌고 가거나 막는다 — 증거가
    필요한 바로 그때 증거가 없어진다. 그래서 참조가 **없어야** 한다.

    DDL이 아니라 스키마를 본다. 값이 잘 베껴졌는지는 위 테스트들이 이미 확인하고,
    여기서 붙드는 것은 "무엇에 묶여 있는가"다.
    """
    targets = {
        fk.column.table.name for fk in PredictionRetrievalModel.__table__.foreign_keys
    }

    assert targets == {"ple_agent_predictions"}
    assert PredictionRetrievalModel.__table__.c.chunk_id.foreign_keys == set()


def test_deleting_the_prediction_takes_the_record_with_it() -> None:
    """기록은 그 생성에 속한다 — 예측이 사라지면 함께 사라져야 고아가 남지 않는다."""

    async def body(session: AsyncSession) -> None:
        await AgentPredictionPgRepository(session).save(
            _prediction(retrievals=(_retrieval(1, chunk_id=11),))
        )
        await session.commit()

        await session.execute(delete(AgentPredictionModel))
        await session.commit()

        rows = (await session.execute(select(PredictionRetrievalModel))).all()
        assert rows == []

    _run(body)


def test_the_read_path_returns_the_record() -> None:
    """한쪽만 매핑하면 왕복시킨 엔티티가 기록을 조용히 잃는다."""

    async def body(session: AsyncSession) -> None:
        repository = AgentPredictionPgRepository(session)
        await repository.save(
            _prediction(
                retrievals=(_retrieval(1, chunk_id=11), _retrieval(2, chunk_id=12))
            )
        )
        await session.commit()

        loaded = await repository.list_by_event(event_slug="summerslam")

        assert [item.rank for item in loaded[0].retrievals] == [1, 2]
        assert [item.chunk_id for item in loaded[0].retrievals] == [11, 12]
        # tzinfo는 SQLite가 안 돌려준다(위 주석) — 시각 자체가 살아 오는지만 본다.
        assert (
            loaded[0].retrievals[0].source_revised_at.replace(tzinfo=UTC) == _REVISED_AT
        )

    _run(body)
