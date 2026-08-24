"""AI LAB 유스케이스 테스트 (Phase 3-1).

시스템 상태가 **실측에서만 나오는지**를 못 박는다 — 특히 LLM 칸이 언제나
`unknown`이어야 한다. 초록불을 만들어 내면 그 순간 이 화면은 거짓말이 된다.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from kayfabe.app.dtos.ai_lab_dto import AiLabOverviewResponse
from kayfabe.app.ports.output.ai_lab_repository import AiLabRepository
from kayfabe.app.services.ai_lab_integrity import (
    CorpusFacts,
    PredictionRow,
    ReportRow,
)
from kayfabe.app.services.ai_lab_knowledge import DocumentRow
from kayfabe.app.use_cases.ai_lab_interactor import AiLabInteractor

_NOW = datetime(2026, 8, 5, tzinfo=UTC)


def _prediction(
    *,
    slug: str = "summerslam",
    label: str = "SummerSlam",
    match_key: str = "m1",
    pick: str = "left",
    generated_at: datetime = _NOW,
    winner_pick: str | None = "left",
) -> PredictionRow:
    return PredictionRow(
        event_slug=slug,
        event_label=label,
        match_key=match_key,
        match_title="Title Match",
        pick=pick,
        pick_name="Someone",
        win_probability=0.8,
        confidence=0.6,
        rationale="2/2 분석이 Someone을(를) 골랐습니다.",
        source="agents",
        generated_at=generated_at,
        winner_pick=winner_pick,
        winner_name="Someone",
    )


class FakeAiLabRepository(AiLabRepository):
    def __init__(
        self,
        *,
        predictions: list[PredictionRow] | None = None,
        reports: list[ReportRow] | None = None,
        corpus: CorpusFacts | None = None,
        documents: list[DocumentRow] | None = None,
        events: int = 11,
    ) -> None:
        self._predictions = predictions or []
        self._reports = reports or []
        self._corpus = corpus or CorpusFacts(0, 0, 0, 0, 0, None)
        self._documents = documents or []
        self._events = events

    async def list_predictions(self) -> list[PredictionRow]:
        return self._predictions

    async def list_reports(self) -> list[ReportRow]:
        return self._reports

    async def corpus_facts(self) -> CorpusFacts:
        return self._corpus

    async def list_documents(self) -> list[DocumentRow]:
        return self._documents

    async def count_events(self) -> int:
        return self._events


class CountingAiLabRepository(FakeAiLabRepository):
    """호출을 센다 — 새 쿼리가 늘지 않았는지 구조로 확인하기 위해서다."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.calls: dict[str, int] = {}

    def _record(self, name: str) -> None:
        self.calls[name] = self.calls.get(name, 0) + 1

    async def list_predictions(self) -> list[PredictionRow]:
        self._record("list_predictions")
        return await super().list_predictions()

    async def list_reports(self) -> list[ReportRow]:
        self._record("list_reports")
        return await super().list_reports()

    async def corpus_facts(self) -> CorpusFacts:
        self._record("corpus_facts")
        return await super().corpus_facts()

    async def list_documents(self) -> list[DocumentRow]:
        self._record("list_documents")
        return await super().list_documents()

    async def count_events(self) -> int:
        self._record("count_events")
        return await super().count_events()


def _interactor(**kwargs) -> AiLabInteractor:
    return AiLabInteractor(repository=FakeAiLabRepository(**kwargs))


def _state(overview: AiLabOverviewResponse, key: str) -> str:
    return next(item.state for item in overview.system if item.key == key)


def _detail(overview: AiLabOverviewResponse, key: str) -> str:
    return next(item.detail for item in overview.system if item.key == key)


class TestSystemStatus:
    @pytest.mark.asyncio
    async def test_the_llm_slot_is_always_unknown(self) -> None:
        overview = await _interactor(predictions=[_prediction()]).get_overview()
        assert _state(overview, "llm") == "unknown"

    @pytest.mark.asyncio
    async def test_an_empty_corpus_reads_as_empty(self) -> None:
        overview = await _interactor().get_overview()
        assert _state(overview, "knowledge") == "empty"

    @pytest.mark.asyncio
    async def test_partial_embeddings_read_as_degraded(self) -> None:
        corpus = CorpusFacts(100, 60, 0, 5, 1, _NOW)
        overview = await _interactor(corpus=corpus).get_overview()
        assert _state(overview, "knowledge") == "degraded"
        assert "40건" in _detail(overview, "knowledge")

    @pytest.mark.asyncio
    async def test_a_fully_embedded_corpus_reads_as_operational(self) -> None:
        corpus = CorpusFacts(668, 668, 0, 40, 1, _NOW)
        overview = await _interactor(corpus=corpus).get_overview()
        assert _state(overview, "knowledge") == "operational"

    @pytest.mark.asyncio
    async def test_no_predictions_leaves_the_engine_empty(self) -> None:
        overview = await _interactor().get_overview()
        assert _state(overview, "engine") == "empty"

    @pytest.mark.asyncio
    async def test_no_reports_leaves_the_agents_empty(self) -> None:
        overview = await _interactor(predictions=[_prediction()]).get_overview()
        assert _state(overview, "agents") == "empty"


class TestOverview:
    @pytest.mark.asyncio
    async def test_recent_predictions_come_newest_first(self) -> None:
        old = _prediction(
            match_key="old", generated_at=datetime(2026, 8, 1, tzinfo=UTC)
        )
        new = _prediction(
            match_key="new", generated_at=datetime(2026, 8, 9, tzinfo=UTC)
        )
        overview = await _interactor(predictions=[old, new]).get_overview()
        assert [r.match_key for r in overview.recent] == ["new", "old"]

    @pytest.mark.asyncio
    async def test_an_ungraded_prediction_is_neither_hit_nor_miss(self) -> None:
        overview = await _interactor(
            predictions=[_prediction(winner_pick=None)]
        ).get_overview()
        assert overview.recent[0].correct is None

    @pytest.mark.asyncio
    async def test_a_graded_prediction_reports_its_result(self) -> None:
        overview = await _interactor(
            predictions=[_prediction(match_key="hit"), _prediction(match_key="miss")]
        ).get_overview()
        assert all(r.correct is True for r in overview.recent)

    @pytest.mark.asyncio
    async def test_coverage_is_measured_against_every_event(self) -> None:
        overview = await _interactor(
            predictions=[_prediction()], events=11
        ).get_overview()
        assert overview.integrity.events_total == 11
        assert overview.integrity.events_covered == 1

    @pytest.mark.asyncio
    async def test_the_confidence_interval_survives_the_schema(self) -> None:
        # 매핑은 라우터가 한다 — app 레이어가 Pydantic을 모르게 두기 위해서다.
        from kayfabe.adapter.inbound.api.v1.ai_lab_router import to_schema

        overview = await _interactor(
            predictions=[_prediction(match_key=f"m{i}") for i in range(12)]
        ).get_overview()
        schema = to_schema(overview)
        assert schema.predictions.hit_rate == 1.0
        assert schema.predictions.hit_rate_low < 1.0
        assert schema.integrity.generalizable is False


class TestNoGeneration:
    """AI LAB은 **읽기만 한다.** 화면 진입이 LLM 호출이 되는 순간 비용이 트래픽에 붙는다."""

    def test_the_read_port_offers_no_way_to_generate(self) -> None:
        methods = {m for m in dir(AiLabRepository) if not m.startswith("_")}
        assert methods == {
            "list_predictions",
            "list_reports",
            "corpus_facts",
            "list_documents",
            "count_events",
        }

    def test_the_ai_lab_modules_do_not_import_any_model_client(self) -> None:
        """import 문만 본다 — 화면 라벨의 "LLM (Gemini)" 같은 문자열에 속지 않는다."""
        import ast
        import inspect

        from kayfabe.adapter.inbound.api.v1 import ai_lab_router
        from kayfabe.app.use_cases import ai_lab_interactor

        banned = ("gemini", "agents", "ontology", "embedding")
        for module in (ai_lab_interactor, ai_lab_router):
            tree = ast.parse(inspect.getsource(module))
            imported: list[str] = []
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    imported.append(node.module)
                elif isinstance(node, ast.Import):
                    imported.extend(alias.name for alias in node.names)
            offenders = [m for m in imported if any(b in m for b in banned)]
            assert offenders == [], f"{module.__name__} imports {offenders}"


class TestAgentAnalysis:
    """Phase 3-3 — 에이전트 성적. **새 쿼리 없이** 기존 두 목록을 잇는다."""

    @pytest.mark.asyncio
    async def test_the_agents_endpoint_reads_only_the_four_existing_queries(
        self,
    ) -> None:
        repository = CountingAiLabRepository(
            predictions=[_prediction(match_key="m1")],
            reports=[ReportRow("summerslam", "m1", "odds", "left", 0.6, "…", ())],
        )
        await AiLabInteractor(repository=repository).get_agents()
        # 새 리포지토리 메서드를 만들지 않았다는 것을 구조로 고정한다.
        assert repository.calls == {
            "list_predictions": 1,
            "list_reports": 1,
            "corpus_facts": 1,
            "count_events": 1,
        }

    @pytest.mark.asyncio
    async def test_agent_accuracy_is_measured_against_the_real_winner(self) -> None:
        rows = [
            _prediction(match_key="m1", pick="left", winner_pick="left"),
            _prediction(match_key="m2", pick="left", winner_pick="right"),
        ]
        reports = [
            # 최종 예측은 m2에서 틀렸지만, odds는 그 경기에서 맞혔다.
            ReportRow("summerslam", "m1", "odds", "left", 0.6, "…", ()),
            ReportRow("summerslam", "m2", "odds", "right", 0.7, "…", ()),
        ]
        result = await _interactor(predictions=rows, reports=reports).get_agents()
        odds = next(a for a in result.agents if a.agent == "odds")
        assert (odds.gradable, odds.correct, odds.incorrect) == (2, 2, 0)
        assert odds.accuracy == 1.0

    @pytest.mark.asyncio
    async def test_the_agents_view_shares_the_integrity_verdict(self) -> None:
        rows = [_prediction(match_key=f"m{i}") for i in range(12)]
        reports = [
            ReportRow(
                "summerslam",
                f"m{i}",
                "rumor",
                "left",
                1.0,
                "…",
                ("https://en.wikipedia.org/wiki/SummerSlam_(2026)",),
            )
            for i in range(12)
        ]
        interactor = _interactor(predictions=rows, reports=reports)
        agents = await interactor.get_agents()
        overview = await interactor.get_overview()
        # 화면마다 다른 무결성이 나오면 어느 쪽도 못 믿는다.
        assert agents.integrity == overview.integrity
        assert agents.integrity.generalizable is False

    @pytest.mark.asyncio
    async def test_the_overview_agent_contract_gains_no_new_fields(self) -> None:
        from kayfabe.adapter.inbound.api.v1.ai_lab_router import to_schema

        overview = await _interactor(
            predictions=[_prediction(match_key="m1")],
            reports=[ReportRow("summerslam", "m1", "odds", "left", 0.6, "…", ())],
        ).get_overview()
        fields = set(to_schema(overview).agents[0].model_dump(by_alias=True))
        # Phase 3-3 필드를 개요에 끼워 넣지 않는다 — 계약이 커지면 되돌리기 어렵다.
        assert fields == {"agent", "reports", "withPick", "opinionRate", "avgWeight"}

    @pytest.mark.asyncio
    async def test_the_schema_keeps_the_denominators(self) -> None:
        from kayfabe.adapter.inbound.api.v1.ai_lab_router import agents_to_schema

        rows = [_prediction(match_key=f"m{i}") for i in range(10)]
        reports = [
            ReportRow(
                "summerslam",
                f"m{i}",
                "odds",
                "left" if i < 9 else "right",
                0.6,
                "…",
                (),
            )
            for i in range(10)
        ]
        schema = agents_to_schema(
            await _interactor(predictions=rows, reports=reports).get_agents()
        )
        odds = schema.agents[0]
        assert (odds.gradable, odds.correct, odds.incorrect) == (10, 9, 1)
        assert odds.accuracy == pytest.approx(0.9)
        assert odds.accuracy_low is not None and odds.accuracy_low < 0.9
        assert odds.uses_knowledge is False


class TestEvaluation:
    """Phase 3-6 — 평가 자격. **성능을 재지 않고 분모를 정한다.**"""

    @staticmethod
    def _document(url: str, *, published: int = 0) -> DocumentRow:
        return DocumentRow(
            source_url=url,
            source_domain="en.wikipedia.org",
            title="doc",
            chunks=3,
            chunks_embedded=3,
            chunks_with_published_at=published,
            first_published_at=None,
            last_collected_at=_NOW,
        )

    @pytest.mark.asyncio
    async def test_it_reuses_the_five_existing_reads(self) -> None:
        repository = CountingAiLabRepository(
            predictions=[_prediction(match_key="m1")],
            reports=[ReportRow("summerslam", "m1", "odds", "left", 0.6, "…", ())],
        )
        await AiLabInteractor(repository=repository).get_evaluation()
        # 새 리포지토리 메서드도 새 쿼리도 만들지 않았다.
        assert repository.calls == {
            "list_predictions": 1,
            "list_reports": 1,
            "list_documents": 1,
            "corpus_facts": 1,
            "count_events": 1,
        }

    @pytest.mark.asyncio
    async def test_a_prediction_made_after_the_result_is_disqualified(self) -> None:
        from kayfabe.adapter.inbound.api.v1.ai_lab_router import evaluation_to_schema

        # 운영 데이터의 모양 그대로: 결과가 기록된 뒤에 예측이 만들어졌다.
        row = _prediction(match_key="m1", generated_at=datetime(2026, 8, 5, tzinfo=UTC))
        row = replace(row, finished_at=datetime(2026, 8, 4, tzinfo=UTC))
        schema = evaluation_to_schema(
            await _interactor(
                predictions=[row],
                reports=[ReportRow("summerslam", "m1", "odds", "left", 0.6, "…", ())],
            ).get_evaluation()
        )
        assert schema.totals.disqualified == 1
        assert schema.totals.eligible == 0
        # **자격이 0건이면 성능은 null이다.** 0%가 아니다.
        assert schema.performance is None
        item = schema.items[0]
        assert item.status == "disqualified"
        assert any(v.code == "temporal_inversion" and v.failed for v in item.verdicts)

    @pytest.mark.asyncio
    async def test_the_evaluation_view_shares_the_integrity_verdict(self) -> None:
        rows = [_prediction(match_key=f"m{i}") for i in range(12)]
        interactor = _interactor(predictions=rows)
        evaluation = await interactor.get_evaluation()
        overview = await interactor.get_overview()
        # 3-0의 경고와 이 자격 판정이 갈리면 어느 쪽도 못 믿는다.
        assert evaluation.integrity == overview.integrity

    @pytest.mark.asyncio
    async def test_an_eligible_sample_keeps_the_integrity_warning(self) -> None:
        """자격이 있어도 표본이 작으면 3-0 경고는 그대로 선다."""
        url = "https://en.wikipedia.org/wiki/Backlash_(2026)"
        row = replace(
            _prediction(match_key="m1", generated_at=datetime(2026, 8, 1, tzinfo=UTC)),
            finished_at=datetime(2026, 8, 4, tzinfo=UTC),
        )
        result = await _interactor(
            predictions=[row],
            reports=[ReportRow("summerslam", "m1", "rumor", "left", 1.0, "…", (url,))],
            documents=[self._document(url, published=3)],
        ).get_evaluation()

        assert result.totals.eligible == 1
        assert result.performance is not None
        assert result.performance.sample == 1
        # 숫자는 내되 경고는 유지된다 — 둘은 다른 층위다.
        assert result.integrity.generalizable is False
        assert result.integrity.reasons

    @pytest.mark.asyncio
    async def test_the_rule_list_is_fixed_even_with_no_predictions(self) -> None:
        from kayfabe.adapter.inbound.api.v1.ai_lab_router import evaluation_to_schema

        schema = evaluation_to_schema(await _interactor().get_evaluation())
        assert schema.totals.predictions == 0
        assert schema.performance is None
        assert [rule.code for rule in schema.rules] == [
            "not_applicable",
            "pending",
            "temporal_inversion",
            "self_reference",
            "unverifiable_corpus",
        ]
        # 보류를 실격으로 적지 않도록 severity를 함께 낸다.
        by_code = {rule.code: rule.severity for rule in schema.rules}
        assert by_code["unverifiable_corpus"] == "hold"
        assert by_code["temporal_inversion"] == "disqualify"


class TestPerformance:
    """Phase 3-5 — 합성 해부. **정확도를 다시 세지 않는다.**"""

    @pytest.mark.asyncio
    async def test_it_reuses_the_four_existing_reads(self) -> None:
        repository = CountingAiLabRepository(
            predictions=[_prediction(match_key="m1")],
            reports=[ReportRow("summerslam", "m1", "odds", "left", 0.6, "…", ())],
        )
        await AiLabInteractor(repository=repository).get_performance()
        # 새 리포지토리 메서드도 새 쿼리도 만들지 않았다는 것을 구조로 고정한다.
        assert repository.calls == {
            "list_predictions": 1,
            "list_reports": 1,
            "corpus_facts": 1,
            "count_events": 1,
        }

    @pytest.mark.asyncio
    async def test_the_performance_view_shares_the_integrity_verdict(self) -> None:
        rows = [_prediction(match_key=f"m{i}") for i in range(12)]
        reports = [
            ReportRow("summerslam", f"m{i}", "rumor", "left", 1.0, "…", ())
            for i in range(12)
        ]
        interactor = _interactor(predictions=rows, reports=reports)
        performance = await interactor.get_performance()
        overview = await interactor.get_overview()
        # 화면마다 다른 무결성이 나오면 어느 쪽도 못 믿는다.
        assert performance.integrity == overview.integrity

    @pytest.mark.asyncio
    async def test_the_inferential_lock_is_a_projection_not_a_new_threshold(
        self,
    ) -> None:
        """새 문턱을 만들지 않는다 — 3-0의 판정을 그대로 옮긴다."""
        result = await _interactor(
            predictions=[_prediction(match_key="m1")],
            reports=[ReportRow("summerslam", "m1", "odds", "left", 0.6, "…", ())],
        ).get_performance()
        assert result.inferential.available is result.integrity.generalizable
        assert result.inferential.reasons == result.integrity.reasons

    @pytest.mark.asyncio
    async def test_a_collapsed_win_probability_still_carries_its_coverage(self) -> None:
        """승률 1.0이 근거의 두께를 뜻하지 않는다 — 둘이 같은 응답에 실린다."""
        from kayfabe.adapter.inbound.api.v1.ai_lab_router import performance_to_schema

        schema = performance_to_schema(
            await _interactor(
                predictions=[
                    _prediction(match_key="m1", pick="0", winner_pick="0"),
                ],
                reports=[
                    ReportRow("summerslam", "m1", "rumor", "0", 1.0, "…", ()),
                    ReportRow("summerslam", "m1", "odds", None, 0.0, "…", ()),
                ],
            ).get_performance()
        )
        item = schema.items[0]
        assert item.agreement == 1.0
        assert item.coverage == pytest.approx(1 / 3)
        assert [(r.agent, r.opinionated) for r in item.reports] == [
            ("rumor", True),
            ("odds", False),
        ]
        assert (schema.totals.singles, schema.totals.multi) == (0, 1)

    @pytest.mark.asyncio
    async def test_the_schema_keeps_the_consensus_denominators(self) -> None:
        from kayfabe.adapter.inbound.api.v1.ai_lab_router import performance_to_schema

        schema = performance_to_schema(
            await _interactor(
                predictions=[
                    _prediction(match_key="m1"),
                    _prediction(match_key="m2", winner_pick=None),
                ],
                reports=[
                    ReportRow("summerslam", "m1", "rumor", "left", 1.0, "…", ()),
                    ReportRow("summerslam", "m2", "rumor", "left", 1.0, "…", ()),
                ],
            ).get_performance()
        )
        level = schema.consensus[0]
        # 미채점은 예측 수에는 들어가고 정답률 분모에서는 빠진다.
        assert (level.answered, level.agreed) == (1, 1)
        assert (level.predictions, level.graded, level.correct) == (2, 1, 1)


class TestKnowledge:
    """Phase 3-4 — 코퍼스에 있는 것과 **실제로 쓰인 것**을 갈라 놓는다."""

    @staticmethod
    def _document(url: str, *, chunks: int = 10) -> DocumentRow:
        return DocumentRow(
            source_url=url,
            source_domain="en.wikipedia.org",
            title="SummerSlam (2026)",
            chunks=chunks,
            chunks_embedded=chunks,
            chunks_with_published_at=0,
            first_published_at=None,
            last_collected_at=_NOW,
        )

    @pytest.mark.asyncio
    async def test_a_corpus_document_no_agent_loaded_stays_unused(self) -> None:
        result = await _interactor(
            predictions=[_prediction(match_key="m1")],
            reports=[ReportRow("summerslam", "m1", "odds", "left", 0.6, "…", ())],
            documents=[self._document("https://en.wikipedia.org/wiki/A")],
        ).get_knowledge()
        assert result.totals.documents == 1
        assert result.totals.used_documents == 0
        assert result.documents[0].used_by_agents == ()

    @pytest.mark.asyncio
    async def test_the_knowledge_view_shares_the_integrity_verdict(self) -> None:
        rows = [_prediction(match_key=f"m{i}") for i in range(12)]
        reports = [
            ReportRow(
                "summerslam",
                f"m{i}",
                "rumor",
                "left",
                1.0,
                "…",
                ("https://en.wikipedia.org/wiki/SummerSlam_(2026)",),
            )
            for i in range(12)
        ]
        interactor = _interactor(
            predictions=rows,
            reports=reports,
            documents=[
                self._document("https://en.wikipedia.org/wiki/SummerSlam_(2026)")
            ],
        )
        knowledge = await interactor.get_knowledge()
        overview = await interactor.get_overview()
        # 발행일 0건이라는 판정의 원인이 바로 이 코퍼스다 — 두 화면이 갈리면 안 된다.
        assert knowledge.integrity == overview.integrity
        assert knowledge.documents[0].used_by_reports == 12

    @pytest.mark.asyncio
    async def test_it_reads_the_documents_but_runs_no_search(self) -> None:
        repository = CountingAiLabRepository(
            predictions=[_prediction(match_key="m1")],
            reports=[ReportRow("summerslam", "m1", "odds", "left", 0.6, "…", ())],
            documents=[self._document("https://en.wikipedia.org/wiki/A")],
        )
        await AiLabInteractor(repository=repository).get_knowledge()
        # 문서 목록 하나만 늘었다 — 임베딩도 검색도 부르지 않는다.
        assert repository.calls == {
            "list_documents": 1,
            "list_predictions": 1,
            "list_reports": 1,
            "corpus_facts": 1,
            "count_events": 1,
        }

    @pytest.mark.asyncio
    async def test_the_schema_keeps_the_used_document_denominator(self) -> None:
        from kayfabe.adapter.inbound.api.v1.ai_lab_router import knowledge_to_schema

        used = "https://en.wikipedia.org/wiki/Used"
        schema = knowledge_to_schema(
            await _interactor(
                predictions=[_prediction(match_key="m1")],
                reports=[
                    ReportRow("summerslam", "m1", "rumor", "left", 1.0, "…", (used,))
                ],
                documents=[
                    self._document(used),
                    self._document("https://en.wikipedia.org/wiki/Unused"),
                ],
            ).get_knowledge()
        )
        assert (schema.totals.used_documents, schema.totals.documents) == (1, 2)
        assert schema.totals.used_document_rate == 0.5
        assert schema.documents[0].used_by_agents == ["rumor"]


class TestPredictionsAgentFilter:
    """Phase 3-3 — Agents 화면에서 넘어오는 `?agent=` 필터."""

    @staticmethod
    def _fixture():
        rows = [_prediction(match_key="m1"), _prediction(match_key="m2")]
        reports = [
            ReportRow("summerslam", "m1", "odds", "left", 0.6, "…", ()),
            ReportRow("summerslam", "m2", "odds", "left", 0.6, "…", ()),
            ReportRow("summerslam", "m1", "storyline", "left", 1.0, "…", ()),
        ]
        return rows, reports

    @pytest.mark.asyncio
    async def test_filtering_by_an_agent_keeps_only_its_predictions(self) -> None:
        rows, reports = self._fixture()
        result = await _interactor(predictions=rows, reports=reports).list_predictions(
            agent="storyline"
        )
        assert [i.match_key for i in result.items] == ["m1"]

    @pytest.mark.asyncio
    async def test_every_real_agent_name_filters(self) -> None:
        rows, reports = self._fixture()
        interactor = _interactor(predictions=rows, reports=reports)
        odds = await interactor.list_predictions(agent="odds")
        storyline = await interactor.list_predictions(agent="storyline")
        rumor = await interactor.list_predictions(agent="rumor")
        assert len(odds.items) == 2
        assert len(storyline.items) == 1
        # rumor는 이 픽스처에 리포트가 없다 — 빈 목록이지 오류가 아니다.
        assert rumor.items == []

    @pytest.mark.asyncio
    async def test_an_unknown_agent_yields_an_empty_list_not_an_error(self) -> None:
        rows, reports = self._fixture()
        result = await _interactor(predictions=rows, reports=reports).list_predictions(
            agent="statistics"
        )
        assert result.items == []
        # 없음은 예외가 아니다 — 집계와 무결성은 여전히 전체를 설명한다.
        assert result.totals.total == 2
        assert result.integrity.sample_size == 2

    @pytest.mark.asyncio
    async def test_no_filter_keeps_everything(self) -> None:
        rows, reports = self._fixture()
        result = await _interactor(predictions=rows, reports=reports).list_predictions()
        assert len(result.items) == 2


class TestListPredictions:
    """Phase 3-2 — 저장된 예측 목록. **LLM도 생성도 없다.**"""

    @pytest.mark.asyncio
    async def test_a_graded_prediction_reports_hit_or_miss(self) -> None:
        rows = [
            _prediction(match_key="hit", pick="left", winner_pick="left"),
            _prediction(match_key="miss", pick="left", winner_pick="right"),
        ]
        result = await _interactor(predictions=rows).list_predictions()
        by_key = {i.match_key: i for i in result.items}
        assert by_key["hit"].correct is True
        assert by_key["miss"].correct is False

    @pytest.mark.asyncio
    async def test_a_prediction_without_a_result_stays_pending(self) -> None:
        result = await _interactor(
            predictions=[_prediction(winner_pick=None)]
        ).list_predictions()
        # Pending은 실패가 아니다 — False로 뭉치면 화면이 "틀렸다"로 읽는다.
        assert result.items[0].correct is None

    @pytest.mark.asyncio
    async def test_agent_reports_are_attached_to_their_own_match(self) -> None:
        rows = [_prediction(match_key="m1"), _prediction(match_key="m2")]
        reports = [
            ReportRow("summerslam", "m1", "odds", "left", 0.52, "배당 1.73", ()),
            ReportRow(
                "summerslam",
                "m1",
                "rumor",
                "left",
                1.0,
                "자료에 따르면 ...",
                ("https://en.wikipedia.org/wiki/SummerSlam_(2026)",),
            ),
        ]
        result = await _interactor(predictions=rows, reports=reports).list_predictions()
        by_key = {i.match_key: i for i in result.items}
        assert [r.agent for r in by_key["m1"].reports] == ["odds", "rumor"]
        assert by_key["m2"].reports == ()

    @pytest.mark.asyncio
    async def test_an_agent_without_an_opinion_keeps_a_null_pick(self) -> None:
        reports = [
            ReportRow(
                "summerslam",
                "m1",
                "storyline",
                None,
                0.0,
                "참고할 서사 자료가 없습니다.",
                (),
            )
        ]
        result = await _interactor(
            predictions=[_prediction()], reports=reports
        ).list_predictions()
        report = result.items[0].reports[0]
        # 의견 없음을 임의의 pick으로 채우지 않는다.
        assert report.pick is None
        assert report.sources == ()

    @pytest.mark.asyncio
    async def test_the_event_filter_lists_only_events_that_have_predictions(
        self,
    ) -> None:
        rows = [
            _prediction(match_key="m1"),
            _prediction(match_key="m2"),
            _prediction(slug="backlash", label="Backlash", match_key="m3"),
        ]
        result = await _interactor(predictions=rows, events=11).list_predictions()
        assert [(e.slug, e.count) for e in result.events] == [
            ("backlash", 1),
            ("summerslam", 2),
        ]

    @pytest.mark.asyncio
    async def test_the_list_carries_the_same_integrity_verdict_as_the_overview(
        self,
    ) -> None:
        rows = [_prediction(match_key=f"m{i}") for i in range(12)]
        reports = [
            ReportRow(
                "summerslam",
                f"m{i}",
                "rumor",
                "left",
                1.0,
                "자료에 따르면 ...",
                ("https://en.wikipedia.org/wiki/SummerSlam_(2026)",),
            )
            for i in range(12)
        ]
        interactor = _interactor(predictions=rows, reports=reports)
        listed = await interactor.list_predictions()
        overview = await interactor.get_overview()
        # 같은 계산을 두 번 만들지 않는다 — 두 화면의 판정이 갈리면 안 된다.
        assert listed.integrity == overview.integrity
        assert listed.totals == overview.predictions
        assert listed.integrity.generalizable is False

    @pytest.mark.asyncio
    async def test_no_predictions_yields_an_empty_list_not_a_zero(self) -> None:
        result = await _interactor().list_predictions()
        assert result.items == []
        assert result.events == []
        # 표본이 없으면 적중률은 0%가 아니라 값이 없다.
        assert result.totals.hit_rate is None

    @pytest.mark.asyncio
    async def test_predictions_come_newest_first(self) -> None:
        old = _prediction(
            match_key="old", generated_at=datetime(2026, 8, 1, tzinfo=UTC)
        )
        new = _prediction(
            match_key="new", generated_at=datetime(2026, 8, 9, tzinfo=UTC)
        )
        result = await _interactor(predictions=[old, new]).list_predictions()
        assert [i.match_key for i in result.items] == ["new", "old"]

    @pytest.mark.asyncio
    async def test_the_schema_keeps_pending_distinct_from_a_miss(self) -> None:
        from kayfabe.adapter.inbound.api.v1.ai_lab_router import predictions_to_schema

        rows = [
            _prediction(match_key="pending", winner_pick=None),
            _prediction(match_key="miss", pick="left", winner_pick="right"),
        ]
        schema = predictions_to_schema(
            await _interactor(predictions=rows).list_predictions()
        )
        by_key = {i.match_key: i for i in schema.items}
        assert by_key["pending"].correct is None
        assert by_key["miss"].correct is False
        assert by_key["pending"].rationale != ""
