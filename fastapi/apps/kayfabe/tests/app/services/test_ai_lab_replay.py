"""예측 재현 (Phase 5).

**이 테스트가 붙드는 것은 "재현이 두 번째 구현이 아니다"라는 것이다.** 합성을
여기서 다시 짜면 규칙이 바뀐 날 둘이 나란히 같은 틀린 답을 내고, 그러면 재현은
아무것도 감시하지 못한다. 그래서 첫 시험은 **생성 경로를 실제로 한 번 돌려**
그 결과를 그대로 재현하는 왕복이다.

계약 여섯:

1. 생성이 만든 예측은 재현에서 **그대로** 나온다.
2. 값이 하나라도 다르면 `diverged`이고, **두 값을 다 싣는다.**
3. 허용 오차가 없다 — 마지막 자리 하나가 달라도 어긋남이다.
4. 카드 드리프트는 **질의 대조**가 잡는다. `pick_name`만 보면 고르지 않은 쪽이
   바뀐 것을 놓친다.
5. 재료가 없으면 `unreplayable`이다 — 실패가 아니라 상태이고, 사유를 말한다.
6. 못 돌리는 단계도 `stages`에 남는다. 빠지면 화면이 "전부 재현됐다"로 읽는다.

실행:

    cd fastapi
    PYTHONUTF8=1 PYTHONPATH=apps uv run pytest \\
        apps/kayfabe/tests/app/services/test_ai_lab_replay.py -q
"""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Sequence
from datetime import UTC, date, datetime

import pytest

from kayfabe.app.dtos.agent_prediction_dto import (
    GeneratePredictionCommand,
    KnowledgeChunk,
    MatchContext,
    MatchOption,
)
from kayfabe.app.ports.output.agent_prediction_repository import (
    AgentPredictionRepository,
)
from kayfabe.app.ports.output.odds_scout_port import OddsScoutPort
from kayfabe.app.ports.output.prediction_knowledge_port import PredictionKnowledgePort
from kayfabe.app.ports.output.rumor_scout_port import RumorScoutPort
from kayfabe.app.ports.output.storyline_analyst_port import StorylineAnalystPort
from kayfabe.app.services import ai_lab_replay
from kayfabe.app.services.ai_lab_integrity import PredictionRow, ReportRow
from kayfabe.app.services.ai_lab_replay import (
    REPLAY_STAGES,
    ReplayStatus,
    replay_prediction,
)
from kayfabe.app.use_cases import ai_prediction_interactor
from kayfabe.app.use_cases.ai_prediction_interactor import AiPredictionInteractor
from kayfabe.domain.entities.agent_prediction import (
    AgentKind,
    AgentPrediction,
    AgentReport,
)

_SLUG = "summerslam"
_MATCH = "ss26-n2-whc"
_NOW = datetime(2026, 8, 4, 12, tzinfo=UTC)

_OPTIONS = (
    MatchOption(pick="left", name="Roman Reigns", is_champion=True),
    MatchOption(pick="right", name="Seth Rollins"),
)

_CONTEXT = MatchContext(
    event_slug=_SLUG,
    event_label="SummerSlam",
    match_key=_MATCH,
    title="World Heavyweight Championship",
    match_format="singles",
    options=_OPTIONS,
    bookmaker_decimal=(1.14, 5.0),
)


# ---------------------------------------------------------------------------
# 생성 경로를 실제로 돌리는 페이크. LLM·DB·네트워크 호출 0회.
# ---------------------------------------------------------------------------


class _Repository(AgentPredictionRepository):
    def __init__(self) -> None:
        self.saved: list[AgentPrediction] = []

    async def list_by_event(self, *, event_slug: str) -> list[AgentPrediction]:
        return list(self.saved)

    async def load_contexts(
        self, *, event_slug: str, match_keys: Sequence[str]
    ) -> list[MatchContext]:
        return [_CONTEXT]

    async def existing_match_keys(self, *, event_slug: str) -> set[str]:
        return set()

    async def save(self, prediction: AgentPrediction) -> None:
        self.saved.append(prediction)


class _Knowledge(PredictionKnowledgePort):
    async def search(self, *, query: str, top_k: int) -> list[KnowledgeChunk]:
        return [KnowledgeChunk(text="서사 요약", source_url="https://wwe.com/x")]


class _Agent:
    def __init__(self, agent: AgentKind, pick: str | None, weight: float) -> None:
        self._agent = agent
        self._pick = pick
        self._weight = weight

    def _report(self) -> AgentReport:
        return AgentReport(
            agent=self._agent,
            pick=self._pick,
            weight=self._weight,
            summary=f"{self._agent} 근거",
            sources=("https://example.test/a",),
        )


class _Storyline(_Agent, StorylineAnalystPort):
    async def analyze(self, context, knowledge) -> AgentReport:
        return self._report()


class _Odds(_Agent, OddsScoutPort):
    async def analyze(self, context) -> AgentReport:
        return self._report()


class _Rumor(_Agent, RumorScoutPort):
    async def analyze(self, context, knowledge) -> AgentReport:
        return self._report()


async def _generate(
    *,
    storyline: tuple[str | None, float] = ("left", 0.8),
    odds: tuple[str | None, float] = ("left", 0.62),
    rumor: tuple[str | None, float] = ("right", 0.55),
) -> AgentPrediction:
    """진짜 코디네이터를 돌려 예측 하나를 만든다."""
    repository = _Repository()
    interactor = AiPredictionInteractor(
        repository,
        _Knowledge(),
        _Storyline(AgentKind.STORYLINE, *storyline),
        _Odds(AgentKind.ODDS, *odds),
        _Rumor(AgentKind.RUMOR, *rumor),
        clock=lambda: _NOW,
    )
    await interactor.generate(GeneratePredictionCommand(event_slug=_SLUG))
    return repository.saved[0]


def _as_rows(
    prediction: AgentPrediction,
) -> tuple[PredictionRow, list[ReportRow]]:
    """저장을 거쳐 감사 화면이 읽는 행으로 옮긴다 (`ai_lab_pg_repository`와 같은 매핑)."""
    row = PredictionRow(
        event_slug=prediction.event_slug,
        event_label="SummerSlam",
        match_key=prediction.match_key,
        match_title=_CONTEXT.title,
        pick=prediction.pick,
        pick_name=prediction.pick_name,
        win_probability=prediction.win_probability,
        confidence=prediction.confidence,
        rationale=prediction.rationale,
        source=str(prediction.source),
        generated_at=prediction.generated_at,
        winner_pick=None,
        winner_name=None,
        event_start_date=date(2026, 8, 10),
        knowledge_query=prediction.knowledge_query,
    )
    reports = [
        ReportRow(
            event_slug=prediction.event_slug,
            match_key=prediction.match_key,
            agent=str(report.agent),
            pick=report.pick,
            weight=report.weight,
            summary=report.summary,
            sources=report.sources,
        )
        for report in prediction.reports
    ]
    return row, reports


# ---------------------------------------------------------------------------
# 1. 왕복 — 생성이 만든 값이 재현에서 그대로 나온다
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_generated_prediction_replays_to_itself() -> None:
    """**재현은 생성의 두 번째 구현이 아니다.**

    같은 함수·같은 상수를 지나므로 저장된 리포트만으로 저장된 결론이 다시 나온다.
    여기가 깨지면 둘 중 하나가 갈라진 것이고, 그때부터 재현은 감시가 아니라 소음이다.
    """
    prediction = await _generate()
    row, reports = _as_rows(prediction)

    result = replay_prediction(row, reports, _OPTIONS)

    assert result.status is ReplayStatus.REPRODUCED
    assert result.mismatches == ()
    assert result.reason is None
    # 질의도 같은 조립을 지났으므로 카드가 그때와 같다고 말할 수 있다.
    assert result.card_unchanged is True


@pytest.mark.asyncio
async def test_the_replay_sees_the_same_numbers_the_screen_shows() -> None:
    """재현이 본 값이 실제로 그 예측의 값이어야 한다 — 빈 비교가 아니다."""
    prediction = await _generate()
    row, reports = _as_rows(prediction)

    # 세 의견 중 둘이 left다. 그 합의가 곧 저장된 confidence다.
    assert row.pick == "left"
    assert 0.0 < row.win_probability < 1.0
    assert replay_prediction(row, reports, _OPTIONS).status is ReplayStatus.REPRODUCED


# ---------------------------------------------------------------------------
# 2·3. 어긋남 — 두 값을 다 싣고, 허용 오차를 두지 않는다
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_changed_conclusion_is_reported_with_both_values() -> None:
    """ "다르다"만으로는 아무것도 못 한다 — 무엇이 무엇으로 달라졌는지가 있어야 한다."""
    prediction = await _generate()
    row, reports = _as_rows(prediction)
    drifted = dataclasses.replace(row, confidence=row.confidence / 2)

    result = replay_prediction(drifted, reports, _OPTIONS)

    assert result.status is ReplayStatus.DIVERGED
    fields = {item.field for item in result.mismatches}
    assert fields == {"confidence"}
    mismatch = result.mismatches[0]
    assert mismatch.stored == repr(drifted.confidence)
    assert mismatch.replayed == repr(row.confidence)


@pytest.mark.asyncio
async def test_the_smallest_possible_difference_is_still_a_difference() -> None:
    """**허용 오차를 두지 않는다.**

    같은 입력이 같은 순서로 같은 연산을 지나므로 오차가 낄 자리가 없고, 여유를
    두면 진짜 드리프트가 그 여유 안에 숨는다.
    """
    prediction = await _generate()
    row, reports = _as_rows(prediction)
    nudged = dataclasses.replace(
        row, win_probability=math.nextafter(row.win_probability, 1.0)
    )

    result = replay_prediction(nudged, reports, _OPTIONS)

    assert result.status is ReplayStatus.DIVERGED
    assert {item.field for item in result.mismatches} == {"win_probability"}


# ---------------------------------------------------------------------------
# 4. 카드 드리프트 — 질의 대조가 증인이다
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_renamed_loser_is_caught_even_though_the_pick_name_still_matches() -> (
    None
):
    """**`pick_name`만 견주면 놓친다.**

    고른 쪽 이름은 그대로인데 고르지 않은 쪽이 바뀐 카드다. 질의는 선택지 이름을
    전부 이어 붙인 값이라 그 변화가 여기서 드러난다 — 그리고 그 사실이 곧
    "지금 카드로 돌린 합성을 얼마나 믿어도 되는가"에 대한 답이다.
    """
    prediction = await _generate()
    row, reports = _as_rows(prediction)
    renamed = (_OPTIONS[0], MatchOption(pick="right", name="Drew McIntyre"))

    result = replay_prediction(row, reports, renamed)

    assert result.card_unchanged is False
    query = next(item for item in result.mismatches if item.field == "knowledge_query")
    assert "Seth Rollins" in query.stored
    assert "Drew McIntyre" in query.replayed
    # 합성 자체는 그대로 재현된다 — 이름이 바뀌어도 선택지 코드와 무게는 같다.
    assert result.status is ReplayStatus.REPRODUCED


@pytest.mark.asyncio
async def test_a_card_drift_alone_does_not_make_the_synthesis_diverged() -> None:
    """질의 어긋남은 **합성의 판정이 아니다.**

    둘은 다른 물음이다 — 하나는 "카드가 그때와 같은가", 다른 하나는 "같은 재료로
    같은 결론이 나오는가"다. 한 칸으로 접으면 화면이 원인을 못 가린다.
    """
    prediction = await _generate()
    row, reports = _as_rows(prediction)
    renamed = (_OPTIONS[0], MatchOption(pick="right", name="Drew McIntyre"))

    result = replay_prediction(row, reports, renamed)

    assert result.status is ReplayStatus.REPRODUCED
    assert result.card_unchanged is False


@pytest.mark.asyncio
async def test_no_recorded_query_means_unknown_not_unchanged() -> None:
    """**`None`은 "같다"가 아니다.** Phase 3 이전 예측에는 견줄 상대가 없다."""
    prediction = await _generate()
    row, reports = _as_rows(prediction)

    result = replay_prediction(
        dataclasses.replace(row, knowledge_query=None), reports, _OPTIONS
    )

    assert result.card_unchanged is None
    assert result.status is ReplayStatus.REPRODUCED


# ---------------------------------------------------------------------------
# 5. 재료가 없는 상태 — 실패가 아니라 사유를 말한다
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_vanished_match_card_leaves_the_synthesis_unreplayable() -> None:
    """카드가 사라지면 그때의 선택지를 알 수 없다. 추정해서 돌리지 않는다."""
    prediction = await _generate()
    row, reports = _as_rows(prediction)

    result = replay_prediction(row, reports, ())

    assert result.status is ReplayStatus.UNREPLAYABLE
    assert result.reason is not None and "선택지" in result.reason
    assert result.card_unchanged is None


@pytest.mark.asyncio
async def test_a_bookmaker_fallback_prediction_never_went_through_synthesis() -> None:
    """폴백은 합성을 지나지 않았다 — 없는 실행을 재현했다고 말하지 않는다."""
    prediction = await _generate()
    row, reports = _as_rows(prediction)

    result = replay_prediction(
        dataclasses.replace(row, source="bookmaker_fallback"), reports, _OPTIONS
    )

    assert result.status is ReplayStatus.UNREPLAYABLE
    assert result.reason is not None and "폴백" in result.reason


@pytest.mark.asyncio
async def test_reports_without_an_opinion_cannot_be_synthesized() -> None:
    """의견이 하나도 없으면 합성은 예외를 낸다. 그 예외가 화면을 깨지 않는다."""
    prediction = await _generate()
    row, reports = _as_rows(prediction)
    silent = [dataclasses.replace(report, pick=None) for report in reports]

    result = replay_prediction(row, silent, _OPTIONS)

    assert result.status is ReplayStatus.UNREPLAYABLE
    assert result.reason is not None and "의견" in result.reason


@pytest.mark.asyncio
async def test_a_report_row_outside_the_entity_contract_is_a_reason_not_a_crash() -> (
    None
):
    """저장된 값이 규약을 벗어나면 **데이터의 문제**로 적는다 — 조용히 통과시키지 않는다."""
    prediction = await _generate()
    row, reports = _as_rows(prediction)
    broken = [dataclasses.replace(reports[0], weight=1.5), *reports[1:]]

    result = replay_prediction(row, broken, _OPTIONS)

    assert result.status is ReplayStatus.UNREPLAYABLE
    assert result.reason is not None and "리포트" in result.reason


# ---------------------------------------------------------------------------
# 6. 못 돌리는 단계도 남는다
# ---------------------------------------------------------------------------


class TestStages:
    def test_every_generation_stage_is_listed(self) -> None:
        """**빠진 단계가 없어야 한다.** 목록에서 빠지면 화면이 "전부 재현됐다"로 읽는다."""
        assert [stage.stage for stage in REPLAY_STAGES] == [
            "knowledge_query",
            "knowledge_retrieval",
            "prompt",
            "model_call",
            "synthesis",
        ]

    def test_only_two_stages_claim_to_be_replayable(self) -> None:
        """실제로 다시 돌아가는 것은 질의 조립과 리포트 합성 둘뿐이다."""
        replayable = {stage.stage for stage in REPLAY_STAGES if stage.replayable}
        assert replayable == {"knowledge_query", "synthesis"}

    def test_every_stage_says_why(self) -> None:
        """못 돌린다는 사실은 칸이 아니라 **문장**으로 적혀야 한다."""
        assert all(stage.note.strip() for stage in REPLAY_STAGES)

    @pytest.mark.asyncio
    async def test_the_stage_map_rides_along_even_when_nothing_replayed(self) -> None:
        result = replay_prediction(_as_rows(await _generate())[0], [], ())
        assert result.status is ReplayStatus.UNREPLAYABLE
        assert result.stages == REPLAY_STAGES


# ---------------------------------------------------------------------------
# 메타 — 생성과 재현이 같은 것을 쓰는지 구조로 확인한다
# ---------------------------------------------------------------------------


class TestSharedWithGeneration:
    """주석이 아니라 **객체 동일성**으로 묶어 둔다. 베낀 날 여기가 깨진다."""

    def test_the_agent_count_is_the_generation_constant(self) -> None:
        assert ai_lab_replay.AGENT_COUNT is ai_prediction_interactor.AGENT_COUNT

    def test_the_query_is_built_by_the_generation_function(self) -> None:
        assert (
            ai_lab_replay.build_knowledge_query
            is ai_prediction_interactor.build_knowledge_query
        )

    def test_the_synthesis_is_the_domain_function(self) -> None:
        from kayfabe.domain.services import prediction_synthesis

        assert ai_lab_replay.synthesize is prediction_synthesis.synthesize
