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
    match_key: str = "m1",
    generated_at: datetime = _NOW,
    winner_pick: str | None = "left",
) -> PredictionRow:
    return PredictionRow(
        event_slug="summerslam",
        event_label="SummerSlam",
        match_key=match_key,
        match_title="Title Match",
        pick="left",
        pick_name="Someone",
        win_probability=0.8,
        confidence=0.6,
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
