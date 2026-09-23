"""계보 사슬 E2E — 생성부터 감사·재현·누수까지 한 번에 (Phase 12).

**조각은 전부 초록인데 사슬이 끊어져 있을 수 있다.** 지금까지의 테스트는 각 마디를
따로 붙들었다 — 생성은 페이크 포트로, 판정·재현·누수는 순수 함수로, 저장은 SQLite로.
그 사이의 매핑(카드 JSON → 선택지, 엔티티 → 행, 행 → 읽기 DTO)은 아무도 끝까지
따라가 보지 않았다.

여기서는 **진짜 리포지토리 둘**(`AgentPredictionPgRepository`·`AiLabPgRepository`)을
같은 SQLite 세션에 물려 한 번에 지나간다. 페이크로 남는 것은 **모델과 검색 두
군데뿐**이고, 그나마 검색 페이크는 **DB에 실제로 심은 청크 행을 읽어서** 돌려준다 —
그래야 "그때 읽었다고 기록된 글"과 "코퍼스에 있는 글"이 같은 값이 된다.

이 파일이 붙드는 주장 넷.

1. **생성이 만든 예측은 DB를 왕복하고도 재현된다** — 질의가 저장·복원되고 선택지가
   `card_json`에서 같은 규칙으로 다시 읽힌다. 순수 테스트는 카드 파싱을 안 지난다.
2. **한 사실이 세 화면에 같은 모양으로 나타난다** — 대회 문서를 읽었다는 사실이
   평가에서는 실격으로, 감사에서는 그 청크의 배지로, 누수에서는 그 문서로 나온다.
3. **읽은 순서가 끝까지 살아남는다** — 프롬프트 순서 → 저장 → 감사 화면.
4. **모델 이름은 경계 어디에서도 새지 않는다**(§11-6) — 직렬화한 JSON 전문을 훑는다.

실행:

    cd fastapi
    PYTHONUTF8=1 PYTHONPATH=apps uv run pytest \\
        apps/kayfabe/tests/test_provenance_chain_e2e.py -q
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Sequence
from datetime import UTC, date, datetime

import pytest
from core.matrix.grid_oracle_database_manager import Base
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

# `outbound.mappers.__init__` ↔ `inbound.api` 순환 회피 — main.py와 같은 순서다.
import kayfabe.adapter.inbound.api.v1.ple_events_router  # noqa: F401
from kayfabe.adapter.inbound.api.v1.ai_lab_router import (
    audit_to_schema,
    evaluation_to_schema,
    leakage_to_schema,
)
from kayfabe.adapter.outbound.orm.agent_prediction_orm import (
    AgentPredictionModel,
    AgentReportModel,
    PredictionRetrievalModel,
)
from kayfabe.adapter.outbound.orm.knowledge_chunk_orm import KnowledgeChunkModel
from kayfabe.adapter.outbound.orm.ple_orm import (
    PleEventModel,
    PleEventStatus,
    PleMatchModel,
)
from kayfabe.adapter.outbound.pg.agent_prediction_pg_repository import (
    AgentPredictionPgRepository,
)
from kayfabe.adapter.outbound.pg.ai_lab_pg_repository import AiLabPgRepository
from kayfabe.app.dtos.agent_prediction_dto import (
    GeneratePredictionCommand,
    KnowledgeChunk,
    MatchContext,
)
from kayfabe.app.ports.output.odds_scout_port import OddsScoutPort
from kayfabe.app.ports.output.prediction_knowledge_port import PredictionKnowledgePort
from kayfabe.app.ports.output.rumor_scout_port import RumorScoutPort
from kayfabe.app.ports.output.storyline_analyst_port import StorylineAnalystPort
from kayfabe.app.services.ai_lab_replay import ReplayStatus
from kayfabe.app.use_cases.ai_lab_interactor import AiLabInteractor
from kayfabe.app.use_cases.ai_prediction_interactor import AiPredictionInteractor
from kayfabe.domain.entities.agent_prediction import (
    AgentKind,
    AgentReport,
    AgentRuntime,
)

_SLUG = "summerslam"
_LABEL = "SummerSlam"
_MATCH = "ss26-n1-undisputed"

_EVENT_DAY = date(2026, 8, 10)
_GENERATED_AT = datetime(2026, 8, 3, 7, tzinfo=UTC)
#: 결과가 **예측 뒤에** 기록됐다 — 시간 규칙을 지난다.
_RESULT_AT = datetime(2026, 8, 11, 7, tzinfo=UTC)
#: 경기(8/10)보다도 예측(8/3)보다도 앞선 개정본 — 어느 규칙에도 안 걸린다.
_CLEAN_REVISION = datetime(2026, 8, 1, 7, tzinfo=UTC)
_COLLECTED_AT = datetime(2026, 8, 2, 7, tzinfo=UTC)

_DOC = "https://en.wikipedia.org/wiki/Cody_Rhodes"
_OTHER_DOC = "https://en.wikipedia.org/wiki/Gunther_(wrestler)"
#: 대회 자체를 다룬 문서. 이것을 읽으면 자기참조로 실격이다.
_OWN_DOC = "https://en.wikipedia.org/wiki/SummerSlam_(2026)"

_CARD = json.dumps(
    {
        "format": "singles",
        "left": {"name": "Cody Rhodes", "isChampion": True},
        "right": {"name": "Gunther"},
        "bookmakerDecimal": {"left": 1.5, "right": 2.6},
    }
)

#: 모델 이름. **응답 어디에도 나오면 안 된다**(§11-6) — 경계 전체를 이 문자열로 훑는다.
_MODEL = "gemini-2.5-flash-e2e"


# ---------------------------------------------------------------------------
# 페이크는 둘뿐이다 — 모델과 검색. 나머지는 전부 실물이다.
# ---------------------------------------------------------------------------


class _Knowledge(PredictionKnowledgePort):
    """**DB에 심은 청크를 그대로 읽어 돌려준다.**

    값을 손으로 지어내면 "그때 읽었다고 기록된 글"과 "코퍼스에 있는 글"이 갈리고,
    그러면 이 테스트가 확인하려는 사슬이 애초에 끊긴 채로 시작한다. 임베딩 검색만
    못 돌릴 뿐(코사인 거리는 SQLite에 없다) 읽는 값은 실물이다.
    """

    def __init__(self, session: AsyncSession, urls: Sequence[str]) -> None:
        self._session = session
        self._urls = list(urls)
        self.queries: list[str] = []

    async def search(self, *, query: str, top_k: int) -> list[KnowledgeChunk]:
        from sqlalchemy import select

        self.queries.append(query)
        rows = (
            (
                await self._session.execute(
                    select(KnowledgeChunkModel).order_by(KnowledgeChunkModel.id)
                )
            )
            .scalars()
            .all()
        )
        picked = [row for row in rows if row.source_url in self._urls][:top_k]
        return [
            KnowledgeChunk(
                text=f"{row.title}\n{row.content}",
                source_url=row.source_url,
                published_at=row.published_at,
                chunk_id=row.id,
                content_hash=row.content_hash,
                source_revision_id=row.source_revision_id,
                source_revised_at=row.source_revised_at,
                distance=0.1 * row.id,
            )
            for row in picked
        ]


class _Agent:
    def __init__(self, agent: AgentKind, pick: str | None, weight: float) -> None:
        self._agent = agent
        self._pick = pick
        self._weight = weight

    def _report(self, chunks: Sequence[KnowledgeChunk]) -> AgentReport:
        return AgentReport(
            agent=self._agent,
            pick=self._pick,
            weight=self._weight,
            summary=f"{self._agent} 근거",
            # 실제 에이전트와 같은 규칙 — 프롬프트에 넣은 청크의 출처만 붙인다.
            sources=tuple(
                dict.fromkeys(c.source_url or "" for c in chunks if c.source_url)
            ),
            runtime=AgentRuntime(
                agent_version=f"{self._agent}@e2e",
                model=_MODEL,
                prompt_version="f9b754e8b82ddb96",
            ),
        )


class _Storyline(_Agent, StorylineAnalystPort):
    async def analyze(self, context: MatchContext, knowledge) -> AgentReport:
        return self._report(knowledge)


class _Rumor(_Agent, RumorScoutPort):
    async def analyze(self, context: MatchContext, knowledge) -> AgentReport:
        return self._report(knowledge)


class _Odds(_Agent, OddsScoutPort):
    async def analyze(self, context: MatchContext) -> AgentReport:
        # 오즈 에이전트는 지식을 쓰지 않는다 — 출처도 모델도 없다.
        return AgentReport(
            agent=self._agent,
            pick=self._pick,
            weight=self._weight,
            summary="배당이 챔피언 쪽에 기울어 있다.",
            runtime=AgentRuntime(agent_version="odds@e2e"),
        )


# ---------------------------------------------------------------------------
# 실물 DB 준비
# ---------------------------------------------------------------------------

_TABLES = [
    PleEventModel.__table__,
    PleMatchModel.__table__,
    AgentPredictionModel.__table__,
    AgentReportModel.__table__,
    PredictionRetrievalModel.__table__,
    KnowledgeChunkModel.__table__,
]


def _chunk(index: int, url: str, title: str) -> KnowledgeChunkModel:
    return KnowledgeChunkModel(
        source_url=url,
        source_domain="en.wikipedia.org",
        title=title,
        content=f"{title} 본문 {index}",
        published_at=None,
        source_revision_id=f"136777{index}",
        source_revised_at=_CLEAN_REVISION,
        content_hash=f"{index}" * 64,
        embedding=None,
        collected_at=_COLLECTED_AT,
    )


async def _seed(urls: Sequence[str]) -> tuple[AsyncSession, object]:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _enforce_foreign_keys(dbapi_connection, _record) -> None:  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(lambda c: Base.metadata.create_all(c, tables=_TABLES))

    session = async_sessionmaker(engine, expire_on_commit=False)()
    session.add(
        PleEventModel(
            id=1,
            slug=_SLUG,
            label=_LABEL,
            month=8,
            year=2026,
            start_date=_EVENT_DAY,
            status=PleEventStatus.FINISHED,
        )
    )
    session.add(
        PleMatchModel(
            id=1,
            event_id=1,
            match_key=_MATCH,
            title="Undisputed WWE Championship",
            format="singles",
            sort_order=1,
            card_json=_CARD,
            winner_pick="left",
            winner_name="Cody Rhodes",
            finished_at=_RESULT_AT,
        )
    )
    for index, url in enumerate(urls, start=1):
        session.add(_chunk(index, url, url.rsplit("/", 1)[-1]))
    await session.commit()
    return session, engine


async def _generate(session: AsyncSession, urls: Sequence[str]) -> _Knowledge:
    """**진짜 코디네이터 + 진짜 저장 어댑터**로 예측 하나를 만든다."""
    knowledge = _Knowledge(session, urls)
    interactor = AiPredictionInteractor(
        AgentPredictionPgRepository(session),
        knowledge,
        _Storyline(AgentKind.STORYLINE, "left", 0.8),
        _Odds(AgentKind.ODDS, "left", 0.6),
        _Rumor(AgentKind.RUMOR, "right", 0.55),
        clock=lambda: _GENERATED_AT,
    )
    summary = await interactor.generate(GeneratePredictionCommand(event_slug=_SLUG))
    assert summary.generated == 1, summary
    await session.commit()
    return knowledge


def _run(body, *, urls: Sequence[str] = (_DOC, _OTHER_DOC)):
    async def go():
        session, engine = await _seed(urls)
        try:
            knowledge = await _generate(session, urls)
            return await body(session, knowledge)
        finally:
            await session.close()
            await engine.dispose()

    return asyncio.run(go())


def _lab(session: AsyncSession) -> AiLabInteractor:
    return AiLabInteractor(AiLabPgRepository(session))


# ---------------------------------------------------------------------------
# 1. 생성 → 저장 → 재현. **카드 파싱까지 왕복한다.**
# ---------------------------------------------------------------------------


def test_a_prediction_survives_the_database_and_replays_to_itself() -> None:
    """순수 테스트가 못 지나는 자리가 둘 있다 — ORM 왕복과 `card_json` 파싱이다.

    재현은 저장된 리포트와 **지금 카드에서 다시 읽은 선택지**로 돌아간다. 두 매핑 중
    하나만 어긋나도 여기서 `diverged`가 된다.
    """

    async def body(session: AsyncSession, _knowledge: _Knowledge) -> None:
        audit = await _lab(session).get_audit(event_slug=_SLUG, match_key=_MATCH)

        assert audit is not None
        assert audit.replay.status is ReplayStatus.REPRODUCED
        assert audit.replay.mismatches == ()
        # 질의가 DB를 왕복하고도 카드에서 다시 만든 값과 같다.
        assert audit.replay.card_unchanged is True

    _run(body)


def test_the_query_that_was_thrown_is_the_query_that_was_stored() -> None:
    """검색에 **실제로 쓴 문자열**과 기록이 같은 값이어야 기록이 증거가 된다."""

    async def body(session: AsyncSession, knowledge: _Knowledge) -> None:
        audit = await _lab(session).get_audit(event_slug=_SLUG, match_key=_MATCH)

        assert audit is not None
        assert knowledge.queries == [audit.knowledge_query]
        assert (
            audit.knowledge_query == "Undisputed WWE Championship Cody Rhodes Gunther"
        )

    _run(body)


def test_the_reading_order_survives_to_the_audit_screen() -> None:
    """순서가 곧 "무엇을 먼저 읽었는가"다. 저장도 조회도 그것을 흔들지 않는다."""

    async def body(session: AsyncSession, _knowledge: _Knowledge) -> None:
        audit = await _lab(session).get_audit(event_slug=_SLUG, match_key=_MATCH)

        assert audit is not None
        assert [e.rank for e in audit.evidence] == [1, 2]
        assert [e.source_url for e in audit.evidence] == [_DOC, _OTHER_DOC]
        # 개정본 식별자도 그때 읽은 값 그대로다.
        assert [e.source_revision_id for e in audit.evidence] == ["1367771", "1367772"]

    _run(body)


def test_editing_the_card_afterwards_is_caught_by_the_replay() -> None:
    """**카드는 판본을 남기지 않는다** — 그래서 재현이 그 사실을 먼저 말해야 한다.

    예측을 만든 뒤 고르지 **않은** 쪽 이름만 바꾼다. `pick_name`은 그대로라 그쪽만
    견주면 아무 일도 없었던 것처럼 보이는데, 질의는 선택지 이름을 전부 이어 붙인
    값이라 여기서 드러난다.
    """

    async def body(session: AsyncSession, _knowledge: _Knowledge) -> None:
        from sqlalchemy import update

        await session.execute(
            update(PleMatchModel)
            .where(PleMatchModel.id == 1)
            .values(card_json=_CARD.replace("Gunther", "Drew McIntyre"))
        )
        await session.commit()

        audit = await _lab(session).get_audit(event_slug=_SLUG, match_key=_MATCH)

        assert audit is not None
        assert audit.pick_name == "Cody Rhodes"  # 고른 쪽은 그대로다.
        assert audit.replay.card_unchanged is False
        [mismatch] = audit.replay.mismatches
        assert mismatch.field == "knowledge_query"
        assert "Gunther" in mismatch.stored
        assert "Drew McIntyre" in mismatch.replayed
        # 선택지 코드와 무게는 그대로라 합성 자체는 다시 나온다.
        assert audit.replay.status is ReplayStatus.REPRODUCED

    _run(body)


def test_a_clean_prediction_is_eligible_all_the_way_through() -> None:
    """**사슬이 통과하는 경우도 못 박는다.** 전부 막히기만 하면 규칙이 살아 있는지 모른다."""

    async def body(session: AsyncSession, _knowledge: _Knowledge) -> None:
        lab = _lab(session)
        evaluation = await lab.get_evaluation()
        leakage = await lab.get_leakage()

        [item] = evaluation.items
        assert item.status == "eligible"
        assert evaluation.performance is not None
        assert evaluation.performance.sample == 1
        # 막힌 것이 없으면 그래프는 빈다 — 오류가 아니다.
        assert leakage.totals.blocked_predictions == 0
        assert leakage.documents == []

    _run(body)


# ---------------------------------------------------------------------------
# 2. 한 사실이 세 화면에 같은 모양으로 나타난다
# ---------------------------------------------------------------------------


def test_reading_the_event_document_shows_up_in_all_three_screens() -> None:
    """대회 자체 문서를 읽었다는 **하나의 사실**이 판정·증거·그래프에 같이 나타난다.

    세 화면이 각자 판정하면 여기서 갈린다 — 평가는 실격인데 감사에는 배지가 없거나,
    그래프가 엉뚱한 문서를 지목하는 식으로.
    """

    async def body(session: AsyncSession, _knowledge: _Knowledge) -> None:
        lab = _lab(session)
        evaluation = await lab.get_evaluation()
        audit = await lab.get_audit(event_slug=_SLUG, match_key=_MATCH)
        leakage = await lab.get_leakage()

        [item] = evaluation.items
        assert item.status == "disqualified"
        assert next(v for v in item.verdicts if v.code == "self_reference").failed

        assert audit is not None
        assert audit.evaluation.status == item.status
        flagged = [e for e in audit.evidence if e.self_reference]
        assert [e.source_url for e in flagged] == [_OWN_DOC]

        [document] = leakage.documents
        assert document.source_url == _OWN_DOC
        assert document.codes == ("self_reference",)
        assert document.predictions[0].status == item.status
        assert leakage.totals.attributed == 1
        assert leakage.totals.unattributed == 0

    _run(body, urls=(_DOC, _OWN_DOC))


def test_the_same_document_is_a_mine_before_the_event_happens() -> None:
    """같은 문서가 **시제만 바꾸면** 누수의 원인에서 앞으로의 지뢰가 된다 (Phase 8).

    누수 그래프는 이미 만들어진 예측을 놓고 "이 문서가 막았다"고 하고, 준비도는
    아직 없는 예측을 놓고 "이 문서가 막을 것이다"라고 한다. 둘이 **같은 문서를
    가리켜야** 두 화면이 같은 코퍼스를 보고 있다는 뜻이다.

    대회 날짜만 앞으로 옮긴다 — 코퍼스도 예측도 그대로다.
    """

    async def body(session: AsyncSession, _knowledge: _Knowledge) -> None:
        from sqlalchemy import update

        lab = _lab(session)
        leakage = await lab.get_leakage()

        await session.execute(
            update(PleEventModel)
            .where(PleEventModel.id == 1)
            .values(start_date=date(2099, 8, 10))
        )
        await session.commit()

        readiness = await lab.get_readiness()

        [event] = readiness.events
        assert event.slug == _SLUG
        # 경기 수는 `outerjoin` + `count`로 세므로 ORM을 왕복해야 확인된다.
        assert event.matches == 1
        assert event.predicted == 1
        assert [mine.source_url for mine in event.mines] == [_OWN_DOC]
        assert event.risk == "disqualify_risk"
        # 뒤를 보는 화면과 앞을 보는 화면이 **같은 문서**를 짚는다.
        assert [doc.source_url for doc in leakage.documents] == [_OWN_DOC]

    _run(body, urls=(_DOC, _OWN_DOC))


def test_the_only_evidence_case_is_reported_as_such_end_to_end() -> None:
    """근거가 그 문서 하나뿐이면 **단독 원인으로 세지 않는다** — 사슬 끝까지 그렇다."""

    async def body(session: AsyncSession, _knowledge: _Knowledge) -> None:
        leakage = await _lab(session).get_leakage()

        [document] = leakage.documents
        [edge] = document.predictions
        assert edge.sole_evidence is True
        assert edge.sole_cause is False
        assert leakage.totals.sole_cause_predictions == 0

    _run(body, urls=(_OWN_DOC,))


# ---------------------------------------------------------------------------
# 3. 경계 — 직렬화한 JSON 전문을 훑는다
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("urls", [(_DOC, _OTHER_DOC), (_DOC, _OWN_DOC)])
def test_the_model_name_never_reaches_the_boundary(urls) -> None:
    """**DB에는 있고 응답에는 없다**(§11-6).

    Phase 4가 모델 이름을 저장하기 시작했으므로, 세 응답을 전부 직렬화해 문자열로
    훑는다 — 키 이름만 보면 어딘가 값으로 섞여 나가는 경우를 놓친다.
    """

    async def body(session: AsyncSession, _knowledge: _Knowledge) -> None:
        lab = _lab(session)
        payloads = [
            audit_to_schema(
                await lab.get_audit(event_slug=_SLUG, match_key=_MATCH)
            ).model_dump_json(by_alias=True),
            evaluation_to_schema(await lab.get_evaluation()).model_dump_json(
                by_alias=True
            ),
            leakage_to_schema(await lab.get_leakage()).model_dump_json(by_alias=True),
        ]

        for payload in payloads:
            assert _MODEL not in payload
            assert "gemini" not in payload.lower()
        # 저장은 됐다 — 없어서 안 나온 것이 아니라 경계가 막은 것이다.
        assert any("agentVersion" in payload for payload in payloads)

    _run(body, urls=urls)
