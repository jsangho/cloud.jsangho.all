"""AI LAB 유스케이스 테스트 (Phase 3-1).

시스템 상태가 **실측에서만 나오는지**를 못 박는다 — 특히 LLM 칸이 언제나
`unknown`이어야 한다. 초록불을 만들어 내면 그 순간 이 화면은 거짓말이 된다.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from kayfabe.app.dtos.ai_lab_dto import AiLabOverviewResponse
from kayfabe.app.ports.output.ai_lab_repository import AiLabRepository
from kayfabe.app.services.ai_lab_integrity import (
    CorpusFacts,
    PredictionRow,
    ReportRow,
)
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
        events: int = 11,
    ) -> None:
        self._predictions = predictions or []
        self._reports = reports or []
        self._corpus = corpus or CorpusFacts(0, 0, 0, 0, 0, None)
        self._events = events

    async def list_predictions(self) -> list[PredictionRow]:
        return self._predictions

    async def list_reports(self) -> list[ReportRow]:
        return self._reports

    async def corpus_facts(self) -> CorpusFacts:
        return self._corpus

    async def count_events(self) -> int:
        return self._events


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
