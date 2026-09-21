"""코디네이터 테스트 — 포트 페이크만 쓴다. LLM·DB·네트워크 호출 0회.

하네스 §10-T6의 완료 판정. 특히 **에이전트 하나가 죽어도 나머지로 합성되는지**와
**전부 죽으면 북메이커로 강등되는지**를 고정한다.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import pytest

from kayfabe.app.dtos.agent_prediction_dto import (
    GeneratePredictionCommand,
    KnowledgeChunk,
    MatchContext,
    MatchOption,
)
from kayfabe.app.ports.output.agent_errors import AgentUnavailableError
from kayfabe.app.ports.output.agent_prediction_repository import (
    AgentPredictionRepository,
)
from kayfabe.app.ports.output.odds_scout_port import OddsScoutPort
from kayfabe.app.ports.output.prediction_knowledge_port import (
    KnowledgeSourceUnavailableError,
    PredictionKnowledgePort,
)
from kayfabe.app.ports.output.rumor_scout_port import RumorScoutPort
from kayfabe.app.ports.output.storyline_analyst_port import StorylineAnalystPort
from kayfabe.app.use_cases.ai_prediction_interactor import AiPredictionInteractor
from kayfabe.domain.entities.agent_prediction import (
    AgentKind,
    AgentPrediction,
    AgentReport,
    PredictionSource,
)

_NOW = datetime(2026, 8, 4, 12, 0, tzinfo=UTC)

_CONTEXT = MatchContext(
    event_slug="summerslam",
    event_label="SummerSlam",
    match_key="ss26-n2-whc",
    title="World Heavyweight Championship",
    match_format="singles",
    options=(
        MatchOption(pick="left", name="Roman Reigns", is_champion=True),
        MatchOption(pick="right", name="Seth Rollins"),
    ),
    bookmaker_decimal=(1.14, 5.0),
)


class FakeRepository(AgentPredictionRepository):
    def __init__(
        self,
        contexts: list[MatchContext] | None = None,
        existing: set[str] | None = None,
    ) -> None:
        self._contexts = contexts if contexts is not None else [_CONTEXT]
        self._existing = existing or set()
        self.saved: list[AgentPrediction] = []
        self.stored: list[AgentPrediction] = []

    async def list_by_event(self, *, event_slug: str) -> list[AgentPrediction]:
        return list(self.stored)

    async def load_contexts(
        self, *, event_slug: str, match_keys: Sequence[str]
    ) -> list[MatchContext]:
        if not match_keys:
            return list(self._contexts)
        return [c for c in self._contexts if c.match_key in set(match_keys)]

    async def existing_match_keys(self, *, event_slug: str) -> set[str]:
        return set(self._existing)

    async def save(self, prediction: AgentPrediction) -> None:
        self.saved.append(prediction)


class FakeKnowledge(PredictionKnowledgePort):
    def __init__(
        self,
        *,
        error: Exception | None = None,
        chunks: list[KnowledgeChunk] | None = None,
    ) -> None:
        self.error = error
        self.queries: list[str] = []
        self._chunks = chunks

    async def search(self, *, query: str, top_k: int) -> list[KnowledgeChunk]:
        if self.error is not None:
            raise self.error
        self.queries.append(query)
        if self._chunks is not None:
            return list(self._chunks)
        return [KnowledgeChunk(text="최근 서사 요약", source_url="https://wwe.com/x")]


class FakeAgent:
    """세 포트가 시그니처만 다르므로 리포트 생성 로직을 공유한다."""

    def __init__(
        self,
        agent: AgentKind,
        pick: str | None = "left",
        weight: float = 0.6,
        error: Exception | None = None,
    ) -> None:
        self.agent = agent
        self.pick = pick
        self.weight = weight
        self.error = error
        self.calls = 0

    def _report(self) -> AgentReport:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return AgentReport(
            agent=self.agent,
            pick=self.pick,
            weight=self.weight,
            summary=f"{self.agent} 근거",
            sources=("https://example.test/a",),
        )


class FakeStoryline(FakeAgent, StorylineAnalystPort):
    def __init__(self, **kwargs: object) -> None:
        FakeAgent.__init__(self, AgentKind.STORYLINE, **kwargs)  # type: ignore[arg-type]

    async def analyze(
        self, context: MatchContext, knowledge: Sequence[KnowledgeChunk]
    ) -> AgentReport:
        return self._report()


class FakeOdds(FakeAgent, OddsScoutPort):
    def __init__(self, **kwargs: object) -> None:
        FakeAgent.__init__(self, AgentKind.ODDS, **kwargs)  # type: ignore[arg-type]

    async def analyze(self, context: MatchContext) -> AgentReport:
        return self._report()


class FakeRumor(FakeAgent, RumorScoutPort):
    def __init__(self, **kwargs: object) -> None:
        FakeAgent.__init__(self, AgentKind.RUMOR, **kwargs)  # type: ignore[arg-type]

    async def analyze(
        self, context: MatchContext, knowledge: Sequence[KnowledgeChunk]
    ) -> AgentReport:
        return self._report()


def build(
    *,
    repository: FakeRepository | None = None,
    knowledge: FakeKnowledge | None = None,
    storyline: FakeStoryline | None = None,
    odds: FakeOdds | None = None,
    rumor: FakeRumor | None = None,
) -> tuple[AiPredictionInteractor, FakeRepository]:
    repo = repository or FakeRepository()
    interactor = AiPredictionInteractor(
        repo,
        knowledge or FakeKnowledge(),
        storyline or FakeStoryline(),
        odds or FakeOdds(),
        rumor or FakeRumor(),
        clock=lambda: _NOW,
    )
    return interactor, repo


@pytest.mark.asyncio
async def test_generates_prediction_from_three_agents() -> None:
    interactor, repo = build()

    summary = await interactor.generate(
        GeneratePredictionCommand(event_slug="summerslam")
    )

    assert (summary.requested, summary.generated, summary.failed) == (1, 1, 0)
    saved = repo.saved[0]
    assert saved.pick == "left"
    assert saved.pick_name == "Roman Reigns"
    assert saved.source is PredictionSource.AGENTS
    # 세 에이전트가 같은 쪽이어도 100%가 아니다 — 상대가 가진 몫이 남는다.
    assert 0.5 < saved.win_probability < 1.0
    assert saved.confidence == 1.0
    assert len(saved.reports) == 3


@pytest.mark.asyncio
async def test_one_dead_agent_does_not_stop_the_others() -> None:
    """하네스 §11-3 — 하나가 죽어도 나머지로 합성된다."""
    interactor, repo = build(rumor=FakeRumor(error=AgentUnavailableError("quota")))

    summary = await interactor.generate(
        GeneratePredictionCommand(event_slug="summerslam")
    )

    assert summary.generated == 1
    saved = repo.saved[0]
    assert saved.source is PredictionSource.AGENTS
    assert len(saved.reports) == 2
    # 셋 중 둘만 답했으므로 확신은 2/3 — 실패가 숫자에 정직하게 드러난다
    assert saved.confidence == pytest.approx(2 / 3)


@pytest.mark.asyncio
async def test_all_agents_dead_falls_back_to_bookmaker() -> None:
    """하네스 §11-4 — 전부 죽어도 화면은 예측을 보여준다. 대신 출처를 밝힌다."""
    interactor, repo = build(
        storyline=FakeStoryline(error=AgentUnavailableError("x")),
        odds=FakeOdds(error=AgentUnavailableError("y")),
        rumor=FakeRumor(error=AgentUnavailableError("z")),
    )

    summary = await interactor.generate(
        GeneratePredictionCommand(event_slug="summerslam")
    )

    assert summary.generated == 1
    saved = repo.saved[0]
    assert saved.source is PredictionSource.BOOKMAKER_FALLBACK
    # 배당이 낮은 쪽(1.14)
    assert saved.pick == "left"
    assert saved.reports == ()
    # 승률은 배당의 내재 확률이다 — 임의의 0.5보다 정직하다.
    assert saved.win_probability > 0.5
    # 에이전트가 아무도 답하지 못했으므로 합의는 없다
    assert saved.confidence == 0.0


@pytest.mark.asyncio
async def test_fallback_impossible_without_odds_is_a_failure_not_a_guess() -> None:
    context = MatchContext(
        event_slug="summerslam",
        event_label="SummerSlam",
        match_key="ss26-n2-contender",
        title="No.1 Contender",
        match_format="multi",
        options=(MatchOption(pick="0", name="Kevin Owens"),),
        bookmaker_decimal=None,
    )
    interactor, repo = build(
        repository=FakeRepository(contexts=[context]),
        storyline=FakeStoryline(error=AgentUnavailableError("x")),
        odds=FakeOdds(error=AgentUnavailableError("y")),
        rumor=FakeRumor(error=AgentUnavailableError("z")),
    )

    summary = await interactor.generate(
        GeneratePredictionCommand(event_slug="summerslam")
    )

    assert (summary.generated, summary.failed) == (0, 1)
    assert repo.saved == []


@pytest.mark.asyncio
async def test_knowledge_failure_degrades_instead_of_failing_the_match() -> None:
    """지식 저장소가 죽어도 오즈 에이전트는 답할 수 있다."""
    interactor, repo = build(
        knowledge=FakeKnowledge(error=KnowledgeSourceUnavailableError("down")),
        storyline=FakeStoryline(pick=None, weight=0.0),
        rumor=FakeRumor(pick=None, weight=0.0),
    )

    summary = await interactor.generate(
        GeneratePredictionCommand(event_slug="summerslam")
    )

    assert summary.generated == 1
    saved = repo.saved[0]
    assert saved.source is PredictionSource.AGENTS
    # 오즈 하나만 의견을 냈다 → 확신 1/3
    assert saved.confidence == pytest.approx(1 / 3)


@pytest.mark.asyncio
async def test_pick_outside_the_card_is_demoted_to_no_opinion() -> None:
    """존재하지 않는 선택지가 득표를 가져가면 승률이 통째로 틀어진다."""
    interactor, repo = build(storyline=FakeStoryline(pick="center", weight=0.9))

    await interactor.generate(GeneratePredictionCommand(event_slug="summerslam"))

    saved = repo.saved[0]
    assert saved.pick == "left"
    demoted = next(r for r in saved.reports if r.agent is AgentKind.STORYLINE)
    assert demoted.pick is None
    # 요약은 근거로 남긴다
    assert demoted.summary == "storyline 근거"


@pytest.mark.asyncio
async def test_existing_predictions_are_skipped_without_force() -> None:
    """같은 경기를 다시 부른다고 LLM 비용을 또 태우지 않는다."""
    storyline = FakeStoryline()
    interactor, repo = build(
        repository=FakeRepository(existing={"ss26-n2-whc"}), storyline=storyline
    )

    summary = await interactor.generate(
        GeneratePredictionCommand(event_slug="summerslam")
    )

    assert (summary.generated, summary.skipped) == (0, 1)
    assert storyline.calls == 0
    assert repo.saved == []


@pytest.mark.asyncio
async def test_force_regenerates_existing_predictions() -> None:
    interactor, repo = build(repository=FakeRepository(existing={"ss26-n2-whc"}))

    summary = await interactor.generate(
        GeneratePredictionCommand(event_slug="summerslam", force=True)
    )

    assert (summary.generated, summary.skipped) == (1, 0)


@pytest.mark.asyncio
async def test_match_keys_narrow_the_target() -> None:
    other = MatchContext(
        event_slug="summerslam",
        event_label="SummerSlam",
        match_key="ss26-n1-hiac",
        title="Hell in a Cell",
        match_format="singles",
        options=(
            MatchOption(pick="left", name="Oba Femi"),
            MatchOption(pick="right", name="Brock Lesnar"),
        ),
        bookmaker_decimal=(1.04, 8.5),
    )
    interactor, repo = build(repository=FakeRepository(contexts=[_CONTEXT, other]))

    summary = await interactor.generate(
        GeneratePredictionCommand(event_slug="summerslam", match_keys=("ss26-n1-hiac",))
    )

    assert summary.requested == 1
    assert repo.saved[0].match_key == "ss26-n1-hiac"


@pytest.mark.asyncio
async def test_listing_does_not_touch_agents_or_knowledge() -> None:
    """조회 경로에서 LLM이 돌면 비용이 트래픽에 비례한다(하네스 §11-1)."""
    storyline, odds, rumor = FakeStoryline(), FakeOdds(), FakeRumor()
    knowledge = FakeKnowledge()
    repo = FakeRepository()
    repo.stored = [
        AgentPrediction(
            event_slug="summerslam",
            match_key="ss26-n2-whc",
            pick="left",
            pick_name="Roman Reigns",
            win_probability=0.78,
            confidence=0.67,
            rationale="근거",
            source=PredictionSource.AGENTS,
            generated_at=_NOW,
            reports=(
                AgentReport(
                    agent=AgentKind.ODDS, pick="left", weight=0.6, summary="배당 우위"
                ),
            ),
        )
    ]
    interactor, _ = build(
        repository=repo,
        knowledge=knowledge,
        storyline=storyline,
        odds=odds,
        rumor=rumor,
    )

    items = await interactor.list_predictions(event_slug="summerslam")

    assert len(items) == 1
    assert items[0].source == "agents"
    assert items[0].reports[0].agent == "odds"
    assert (storyline.calls, odds.calls, rumor.calls) == (0, 0, 0)
    assert knowledge.queries == []


@pytest.mark.asyncio
async def test_rationale_quotes_the_agents_without_another_llm_call() -> None:
    interactor, repo = build()

    await interactor.generate(GeneratePredictionCommand(event_slug="summerslam"))

    rationale = repo.saved[0].rationale
    assert "Roman Reigns" in rationale
    assert "storyline 근거" in rationale


class TestRetrievalRecord:
    """무엇을 읽고 만든 예측인가 (Phase 3-13 Stage 4).

    출처 URL은 이미 리포트에 남는다. 그것으로 부족한 이유는 **URL이 같아도 개정본이
    다르면 다른 글**이기 때문이다 — 위키 문서는 경기 전후로 계속 고쳐진다. 그래서
    그때 읽은 개정본을 예측에 붙여 둔다.
    """

    @staticmethod
    def _chunks() -> list[KnowledgeChunk]:
        return [
            KnowledgeChunk(
                text="먼저 읽은 글",
                source_url="https://en.wikipedia.org/wiki/SummerSlam_(2026)",
                chunk_id=11,
                content_hash="a" * 64,
                source_revision_id="1367773770",
                source_revised_at=datetime(2026, 8, 5, 3, 7, 53, tzinfo=UTC),
                published_at=None,
                distance=0.21,
            ),
            KnowledgeChunk(
                text="나중에 읽은 글",
                source_url="https://en.wikipedia.org/wiki/Oba_Femi",
                chunk_id=12,
                content_hash="b" * 64,
                source_revision_id="1367711306",
                source_revised_at=datetime(2026, 8, 4, 18, 40, 31, tzinfo=UTC),
                distance=0.33,
            ),
        ]

    @pytest.mark.asyncio
    async def test_it_records_what_went_into_the_prompt_in_reading_order(self) -> None:
        interactor, repo = build(knowledge=FakeKnowledge(chunks=self._chunks()))

        await interactor.generate(GeneratePredictionCommand(event_slug="summerslam"))

        retrievals = repo.saved[0].retrievals
        assert [item.rank for item in retrievals] == [1, 2]
        # **검색이 돌려준 순서 그대로다** — 유사도 순위가 아니라 읽은 순서를 적는다.
        assert [item.chunk_id for item in retrievals] == [11, 12]
        assert [item.source_revision_id for item in retrievals] == [
            "1367773770",
            "1367711306",
        ]
        assert [item.distance for item in retrievals] == [0.21, 0.33]

    @pytest.mark.asyncio
    async def test_the_revision_is_copied_not_referenced(self) -> None:
        """재수집이 청크를 지워도 남아야 하므로 값을 베껴 둔다."""
        interactor, repo = build(knowledge=FakeKnowledge(chunks=self._chunks()))

        await interactor.generate(GeneratePredictionCommand(event_slug="summerslam"))

        first = repo.saved[0].retrievals[0]
        assert first.source_url == "https://en.wikipedia.org/wiki/SummerSlam_(2026)"
        assert first.content_hash == "a" * 64
        assert first.source_revised_at == datetime(2026, 8, 5, 3, 7, 53, tzinfo=UTC)

    @pytest.mark.asyncio
    async def test_a_failed_search_records_nothing(self) -> None:
        """조회가 실패하면 읽은 것이 없다 — 빈 기록이 사실이다."""
        interactor, repo = build(
            knowledge=FakeKnowledge(error=KnowledgeSourceUnavailableError("down"))
        )

        await interactor.generate(GeneratePredictionCommand(event_slug="summerslam"))

        assert repo.saved[0].retrievals == ()

    @pytest.mark.asyncio
    async def test_a_bookmaker_fallback_still_records_what_was_read(self) -> None:
        """아무도 답하지 못했어도 그 청크들은 프롬프트에 들어갔다.

        폴백은 "에이전트가 의견을 못 냈다"는 사실이지 "아무것도 안 읽었다"가 아니다.
        여기서 기록을 빼면 근거 없는 예측과 구분되지 않는다.
        """
        dead = AgentUnavailableError("quota")
        interactor, repo = build(
            knowledge=FakeKnowledge(chunks=self._chunks()),
            storyline=FakeStoryline(error=dead),
            odds=FakeOdds(error=dead),
            rumor=FakeRumor(error=dead),
        )

        await interactor.generate(GeneratePredictionCommand(event_slug="summerslam"))

        saved = repo.saved[0]
        assert saved.source is PredictionSource.BOOKMAKER_FALLBACK
        assert [item.rank for item in saved.retrievals] == [1, 2]
