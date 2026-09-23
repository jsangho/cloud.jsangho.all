"""실행 조건의 저장 경로 (Phase 4).

앞 파일(`test_agent_runtime_versions.py`)이 "에이전트가 옳은 값을 만드는가"를 봤다면,
여기서 보는 것은 **그 값이 DB를 왕복하고도 같은 말을 하는가**다. 한쪽만 매핑하면
왕복시킨 엔티티가 기록을 조용히 잃고, 그 사실은 몇 달 뒤 감사할 때 드러난다.

붙드는 주장은 둘이다.

1. **기록이 있는 행과 없는 행이 구분된다.** Phase 4 이전 리포트는 세 칸이 NULL이고
   백필하지 않는다 — 그때 어떤 모델·지시문이었는지 아무도 모르므로 지금 값을 적으면
   없던 사실을 만드는 것이 된다. 그 행은 `runtime=None`으로 돌아와야 한다.
2. **`agent_version`이 기록 유무의 기준이다.** `model_version`으로 가리면 LLM을 쓰지
   않는 오즈 에이전트의 기록이 통째로 "기록 없음"이 되어, 기록하지 않은 옛 행과
   같은 것이 되어 버린다.

SQLite 인메모리에서 **실제 쿼리를 돌린다** — production DB를 쓰지 않는다.

실행:

    cd fastapi
    PYTHONUTF8=1 PYTHONPATH=apps uv run pytest \
        apps/kayfabe/tests/adapter/outbound/pg/test_agent_report_runtime.py -q
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

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
)
from kayfabe.adapter.outbound.pg.agent_prediction_pg_repository import (  # noqa: E402
    AgentPredictionPgRepository,
)
from kayfabe.domain.entities.agent_prediction import (  # noqa: E402
    AgentKind,
    AgentPrediction,
    AgentReport,
    AgentRuntime,
    PredictionSource,
)

_TABLES = [
    PleEventModel.__table__,
    AgentPredictionModel.__table__,
    AgentReportModel.__table__,
    PredictionRetrievalModel.__table__,
]

_GENERATED_AT = datetime(2026, 9, 23, 4, 12, 0, tzinfo=UTC)
_URL = "https://en.wikipedia.org/wiki/Cody_Rhodes"


def _prediction(*reports: AgentReport) -> AgentPrediction:
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
        reports=reports,
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


def test_runtime_survives_the_round_trip() -> None:
    async def body(session: AsyncSession) -> None:
        repository = AgentPredictionPgRepository(session)
        await repository.save(
            _prediction(
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
                )
            )
        )
        await session.commit()

        row = (await session.scalars(select(AgentReportModel))).one()
        assert row.model_version == "gemini-3.6-flash"
        assert row.prompt_version == "f9b754e8b82ddb96"
        assert row.agent_version == "storyline@1"

        # 읽는 쪽도 채운다 — 한쪽만 매핑하면 왕복이 기록을 조용히 잃는다.
        [prediction] = await repository.list_by_event(event_slug="summerslam")
        runtime = prediction.reports[0].runtime
        assert runtime is not None
        assert runtime.model == "gemini-3.6-flash"
        assert runtime.prompt_version == "f9b754e8b82ddb96"
        assert runtime.agent_version == "storyline@1"

    _run(body)


def test_a_report_without_a_model_is_not_mistaken_for_an_unrecorded_one() -> None:
    """오즈 에이전트는 모델이 없다. **그래도 기록은 있다.**

    `model_version`으로 기록 유무를 가리면 이 행이 Phase 4 이전 행과 같아진다 —
    "LLM을 안 쓰는 축"과 "아무것도 남기지 않던 시절"은 전혀 다른 사실이다.
    """

    async def body(session: AsyncSession) -> None:
        repository = AgentPredictionPgRepository(session)
        await repository.save(
            _prediction(
                AgentReport(
                    agent=AgentKind.ODDS,
                    pick="left",
                    weight=0.6,
                    summary="배당 1.6으로 가장 낮습니다.",
                    runtime=AgentRuntime(agent_version="odds@1"),
                )
            )
        )
        await session.commit()

        row = (await session.scalars(select(AgentReportModel))).one()
        assert row.model_version is None
        assert row.prompt_version is None
        assert row.agent_version == "odds@1"

        [prediction] = await repository.list_by_event(event_slug="summerslam")
        runtime = prediction.reports[0].runtime
        assert runtime is not None
        assert runtime.agent_version == "odds@1"
        assert runtime.model is None

    _run(body)


def test_legacy_rows_stay_unrecorded() -> None:
    """**Phase 4 이전 행은 비어 있는 채로 돌아온다.**

    마이그레이션이 세 칸을 NULL로 더했고 백필하지 않았다. 읽는 쪽이 그것을
    `runtime=None`으로 옮겨야, 화면과 감사가 "기록이 없다"고 정확히 말할 수 있다.
    빈 문자열이나 기본 판 이름으로 채우면 그 순간 없던 사실이 생긴다.
    """

    async def body(session: AsyncSession) -> None:
        repository = AgentPredictionPgRepository(session)
        # 저장 경로를 거치지 않고 옛 모양의 행을 직접 넣는다 — 마이그레이션 직후
        # 운영 DB에 남아 있는 상태 그대로다.
        session.add(
            AgentPredictionModel(
                event_id=1,
                match_key="ss26-legacy",
                pick="left",
                pick_name="Cody Rhodes",
                win_probability=0.7,
                confidence=0.5,
                rationale="근거",
                source="agents",
                generated_at=_GENERATED_AT,
                reports=[
                    AgentReportModel(
                        agent="storyline",
                        pick="left",
                        weight=0.8,
                        summary="옛 리포트",
                        sources=_URL,
                    )
                ],
            )
        )
        await session.commit()

        [prediction] = await repository.list_by_event(event_slug="summerslam")
        report = prediction.reports[0]
        # 의견은 그대로 살아 있다 — 잃은 것은 실행 조건뿐이다.
        assert report.pick == "left"
        assert report.sources == (_URL,)
        assert report.runtime is None

    _run(body)
