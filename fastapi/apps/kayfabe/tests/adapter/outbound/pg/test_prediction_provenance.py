"""예측 하나의 계보를 **DB만으로 재구성할 수 있는가** (Phase 3).

로드맵 Phase 3의 완료 조건이 그대로 이 파일의 주장이다:

> 특정 prediction 하나를 지정했을 때, 어떤 시각에 어떤 agent/model/prompt가
> 어떤 corpus revision과 retrieval 결과를 사용했는지를 DB에서 재구성할 수 있다.

**"재구성"의 기준을 엄격하게 잡는다.** 식별자만 남아 있고 그것이 가리키던 것이
사라졌다면 재구성이 아니다. 그래서 Phase 3이 두 칸을 더했다:

* `knowledge_query` — 질의는 경기 제목과 선택지 이름에서 만들어지므로 파생값처럼
  보이지만, **카드가 바뀌면 재료가 사라진다.** 경기 행이 없어진 예측이 이미 하나
  있다(`withdrawn_match`). 그 예측의 질의는 지금 어디에서도 복원되지 않는다.
* `content` — `content_hash`는 같은 글인지 **대조**만 해 준다. 재수집이 옛 청크를
  지우면(`replace_document_chunks`) 원문은 세상에서 사라지고, 해시는 "무엇이었는지"에
  답하지 못한다.

SQLite 인메모리에서 실제 쿼리를 돌린다 — production DB를 쓰지 않는다.

실행:

    cd fastapi
    PYTHONUTF8=1 PYTHONPATH=apps uv run pytest \
        apps/kayfabe/tests/adapter/outbound/pg/test_prediction_provenance.py -q
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from core.matrix.grid_oracle_database_manager import Base
from sqlalchemy import delete, select
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
)
from kayfabe.adapter.outbound.pg.agent_prediction_pg_repository import (  # noqa: E402
    AgentPredictionPgRepository,
)
from kayfabe.domain.entities.agent_prediction import (  # noqa: E402
    AgentKind,
    AgentPrediction,
    AgentReport,
    AgentRuntime,
    KnowledgeRetrieval,
    PredictionSource,
)

_TABLES = [
    PleEventModel.__table__,
    PleMatchModel.__table__,
    AgentPredictionModel.__table__,
    AgentReportModel.__table__,
    PredictionRetrievalModel.__table__,
]

_GENERATED_AT = datetime(2026, 9, 23, 4, 12, 0, tzinfo=UTC)
_REVISED_AT = datetime(2026, 9, 19, 16, 4, 27, tzinfo=UTC)
_URL = "https://en.wikipedia.org/wiki/Cody_Rhodes"
_QUERY = "Undisputed WWE Championship Cody Rhodes Drew McIntyre"
_CHUNK_TEXT = (
    "Rhodes entered the feud after the Royal Rumble victory, and the storyline "
    "has framed the title match as the payoff of a two-year arc."
)


def _prediction() -> AgentPrediction:
    """기록이 **전부 있는** 예측 하나. Phase 3 이후 생성 경로가 만드는 모양이다."""
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
                sources=(_URL,),
                runtime=AgentRuntime(
                    agent_version="storyline@1",
                    model="gemini-3.6-flash",
                    prompt_version="f9b754e8b82ddb96",
                ),
            ),
        ),
        retrievals=(
            KnowledgeRetrieval(
                rank=1,
                chunk_id=8821,
                source_url=_URL,
                content_hash="9f2b" * 16,
                content=_CHUNK_TEXT,
                source_revision_id="1375717989",
                source_revised_at=_REVISED_AT,
                distance=0.4386,
            ),
        ),
        knowledge_query=_QUERY,
    )


async def _seed() -> tuple[AsyncSession, object]:
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
        )
    )
    session.add(
        PleMatchModel(
            id=1,
            event_id=1,
            match_key="ss26-n1-undisputed",
            title="Undisputed WWE Championship",
            format="singles",
            card_json="{}",
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


def test_every_provenance_question_has_an_answer_in_the_db() -> None:
    """로드맵 Q1~Q5를 **행에서 직접** 읽는다. 이 테스트가 Phase 3의 완료 조건이다."""

    async def body(session: AsyncSession) -> None:
        repository = AgentPredictionPgRepository(session)
        await repository.save(_prediction())
        await session.commit()

        row = (await session.scalars(select(AgentPredictionModel))).one()
        report = (await session.scalars(select(AgentReportModel))).one()
        chunk = (await session.scalars(select(PredictionRetrievalModel))).one()

        # Q1 언제 생성됐는가
        assert row.generated_at.replace(tzinfo=UTC) == _GENERATED_AT
        # Q2 어떤 agent/model/prompt였는가
        assert (report.agent, report.model_version, report.prompt_version) == (
            "storyline",
            "gemini-3.6-flash",
            "f9b754e8b82ddb96",
        )
        assert report.agent_version == "storyline@1"
        # Q3 무엇을 물었고, 실제로 어떤 글을 읽었는가
        assert row.knowledge_query == _QUERY
        assert chunk.rank == 1
        assert chunk.content == _CHUNK_TEXT
        # Q4 그 글은 어떤 개정본인가
        assert chunk.source_url == _URL
        assert chunk.source_revision_id == "1375717989"
        # Q5 그 개정본은 예측보다 먼저인가
        assert chunk.source_revised_at.replace(tzinfo=UTC) < _GENERATED_AT

    _run(body)


def test_the_snapshot_survives_the_match_disappearing() -> None:
    """**경기가 카드에서 사라져도 계보는 남는다.**

    예측은 경기를 FK가 아니라 `(event_id, match_key)` 문자열로 가리킨다. 그래서
    대진이 바뀌면 경기 행만 사라지는데, 질의를 그때그때 파생시키는 구조였다면
    **이 순간 질의가 영영 사라진다** — 재료가 경기 제목과 선택지 이름이기 때문이다.
    운영에 이미 그런 예측이 하나 있다(`withdrawn_match`).
    """

    async def body(session: AsyncSession) -> None:
        repository = AgentPredictionPgRepository(session)
        await repository.save(_prediction())
        await session.commit()

        await session.execute(delete(PleMatchModel))
        await session.commit()

        row = (await session.scalars(select(AgentPredictionModel))).one()
        assert row.knowledge_query == _QUERY

        [prediction] = await repository.list_by_event(event_slug="summerslam")
        assert prediction.knowledge_query == _QUERY
        assert prediction.retrievals[0].content == _CHUNK_TEXT

    _run(body)


def test_the_round_trip_does_not_drop_the_new_columns() -> None:
    """읽는 쪽도 채운다 — 한쪽만 매핑하면 왕복이 기록을 조용히 잃는다."""

    async def body(session: AsyncSession) -> None:
        repository = AgentPredictionPgRepository(session)
        await repository.save(_prediction())
        await session.commit()

        [prediction] = await repository.list_by_event(event_slug="summerslam")

        assert prediction.knowledge_query == _QUERY
        assert prediction.retrievals[0].content == _CHUNK_TEXT
        assert prediction.retrievals[0].content_hash == "9f2b" * 16

    _run(body)


def test_a_legacy_prediction_keeps_nulls_instead_of_invented_values() -> None:
    """**백필하지 않는다.** 기록 전 예측은 두 칸이 NULL로 남아야 한다.

    지금 코퍼스에서 다시 검색해 채우면 "그때 읽은 것"이 아니라 "지금 검색되는 것"을
    적는 것이 된다 — Phase 3-13이 검색 기록을 비워 둔 것과 같은 이유다. 빈 것이
    정직한 상태이고, 빈 것과 기록된 것이 구분돼야 그 정직함이 쓸모를 갖는다.
    """

    async def body(session: AsyncSession) -> None:
        repository = AgentPredictionPgRepository(session)
        await repository.save(
            AgentPrediction(
                event_slug="summerslam",
                match_key="ss26-n2-legacy",
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
                        summary="옛 리포트",
                    ),
                ),
                retrievals=(KnowledgeRetrieval(rank=1, source_url=_URL),),
            )
        )
        await session.commit()

        row = (await session.scalars(select(AgentPredictionModel))).one()
        chunk = (await session.scalars(select(PredictionRetrievalModel))).one()

        assert row.knowledge_query is None
        assert chunk.content is None

    _run(body)
