"""합성 해부 집계 테스트 (Phase 3-5).

이 화면은 **정확도를 재지 않는다.** 그래서 여기서 못 박는 것도 정확도가 아니라
분모다 — 무엇을 세고 무엇을 안 세는가.

3-0·3-3에서 가져온 규칙 셋을 그대로 지키는지 본다.
- 북메이커 폴백은 **통째로** 빠진다 (예측·리포트 양쪽에서).
- 미채점(`winner_pick is None`)은 오답이 아니다 — `correct=None`이다.
- 의견 없음(`pick is None`)은 오답이 아니고 **동의도 분모에도 안 들어간다.**

그리고 이 화면에만 있는 규칙 하나: **비율이 없으면 `None`이지 0.0이 아니다.**
"""

from __future__ import annotations

from datetime import UTC, datetime

from kayfabe.app.services.ai_lab_integrity import PredictionRow, ReportRow
from kayfabe.app.services.ai_lab_performance import (
    AGENT_COUNT,
    summarize_performance,
)

_NOW = datetime(2026, 8, 5, tzinfo=UTC)


def _prediction(
    *,
    match_key: str = "m1",
    pick: str = "left",
    win_probability: float = 0.8,
    confidence: float = 0.667,
    winner_pick: str | None = "left",
    source: str = "agents",
) -> PredictionRow:
    return PredictionRow(
        event_slug="summerslam",
        event_label="SummerSlam",
        match_key=match_key,
        match_title="Title Match",
        pick=pick,
        pick_name="Someone",
        win_probability=win_probability,
        confidence=confidence,
        rationale="…",
        source=source,
        generated_at=_NOW,
        winner_pick=winner_pick,
        winner_name="Someone",
    )


def _report(
    *,
    agent: str = "rumor",
    match_key: str = "m1",
    pick: str | None = "left",
    weight: float = 1.0,
) -> ReportRow:
    return ReportRow(
        event_slug="summerslam",
        match_key=match_key,
        agent=agent,
        pick=pick,
        weight=weight,
        summary="…",
        sources=(),
    )


class TestDenominators:
    def test_the_bookmaker_fallback_is_dropped_whole(self) -> None:
        """폴백은 합성이라 부를 것이 없다 — 예측도 그 리포트도 빠진다."""
        totals, consensus, contributions, items = summarize_performance(
            [
                _prediction(match_key="m1"),
                _prediction(match_key="m2", source="bookmaker_fallback"),
            ],
            [
                _report(match_key="m1", agent="rumor"),
                _report(match_key="m2", agent="odds", weight=0.5),
            ],
        )
        assert totals.predictions == 2
        assert totals.bookmaker_fallback == 1
        assert totals.graded == 1
        assert [i.match_key for i in items] == ["m1"]
        # 폴백 경기의 리포트가 기여 집계에 새어 들어오면 안 된다.
        assert [c.agent for c in contributions] == ["rumor"]
        assert sum(level.predictions for level in consensus) == 1

    def test_an_ungraded_prediction_is_neither_hit_nor_miss(self) -> None:
        totals, consensus, _, items = summarize_performance(
            [_prediction(winner_pick=None)], [_report()]
        )
        assert items[0].correct is None
        assert (totals.graded, totals.correct, totals.incorrect) == (0, 0, 0)
        # 미채점은 정답률 분모에서 빠지지만 예측 수에서는 빠지지 않는다.
        assert consensus[0].predictions == 1
        assert consensus[0].graded == 0

    def test_no_opinion_is_not_a_wrong_answer(self) -> None:
        _, _, contributions, items = summarize_performance(
            [_prediction()],
            [
                _report(agent="rumor", pick="left"),
                _report(agent="odds", pick=None, weight=0.0),
            ],
        )
        item = items[0]
        # 동의도 분모는 **의견 수**다 — 의견 없음이 들어가면 1/2로 떨어진다.
        assert item.agreement == 1.0
        assert item.coverage == 1 / AGENT_COUNT
        assert [(r.agent, r.opinionated) for r in item.reports] == [
            ("rumor", True),
            ("odds", False),
        ]
        odds = next(c for c in contributions if c.agent == "odds")
        assert (odds.reports, odds.opinions) == (1, 0)

    def test_a_prediction_with_no_reports_has_no_agreement(self) -> None:
        _, _, _, items = summarize_performance([_prediction()], [])
        assert items[0].agreement is None
        assert items[0].coverage == 0.0

    def test_a_prediction_whose_reports_all_abstained_has_no_agreement(self) -> None:
        """의견이 0이면 나눌 것이 없다 — 0.0으로 채우면 '아무도 동의 안 했다'가 된다."""
        _, _, _, items = summarize_performance(
            [_prediction()], [_report(pick=None, weight=0.0)]
        )
        assert items[0].agreement is None
        assert items[0].coverage == 0.0

    def test_no_predictions_yields_empty_lists(self) -> None:
        totals, consensus, contributions, items = summarize_performance([], [])
        assert (totals.predictions, totals.graded, totals.correct) == (0, 0, 0)
        assert (consensus, contributions, items) == ([], [], [])


class TestCoverage:
    def test_one_opinion_at_full_weight_still_reports_a_third_coverage(self) -> None:
        """**승률 1.000이 근거의 두께를 뜻하지 않는다.**

        다파전에서 의견이 하나뿐이고 그 weight가 1.0이면 분포가 붕괴해 승률이
        1.000이 된다. 화면이 그 숫자만 세우면 가장 얕은 예측이 가장 확신에 찬
        예측으로 읽히므로, coverage를 반드시 함께 낸다.
        """
        _, _, _, items = summarize_performance(
            [_prediction(pick="0", win_probability=1.0, confidence=1 / 3)],
            [
                _report(agent="rumor", pick="0", weight=1.0),
                _report(agent="odds", pick=None, weight=0.0),
            ],
        )
        item = items[0]
        assert item.win_probability == 1.0
        assert item.agreement == 1.0
        assert item.coverage == 1 / AGENT_COUNT
        # 저장된 confidence를 재현한다: agreement × coverage.
        assert item.confidence == item.agreement * item.coverage

    def test_coverage_never_exceeds_one(self) -> None:
        """중복 리포트로 분자가 커져도 100%를 넘지 않는다 — 합성 코드와 같은 상한."""
        _, _, _, items = summarize_performance(
            [_prediction()],
            [_report(agent=f"a{i}", pick="left") for i in range(AGENT_COUNT + 2)],
        )
        assert items[0].coverage == 1.0

    def test_the_coverage_denominator_matches_the_generator(self) -> None:
        """분모를 도메인 열거형에서 세는 것이 생성 경로의 상수와 어긋나지 않는지.

        어긋나면 화면의 coverage가 저장된 `confidence`를 더 이상 재현하지 못한다.
        """
        from kayfabe.app.use_cases.ai_prediction_interactor import AGENT_COUNT as GEN

        assert AGENT_COUNT == GEN


class TestConsensus:
    def test_the_same_confidence_can_hold_two_different_situations(self) -> None:
        """`0.667`에는 '2명이 답해 둘 다 동의'와 '3명이 답해 2명 동의'가 함께 있다.

        곱으로 묶으면 한 줄로 접히고 근거의 두께 차이가 사라진다.
        """
        _, consensus, _, _ = summarize_performance(
            [_prediction(match_key="m1"), _prediction(match_key="m2")],
            [
                # m1 — 둘이 답해 둘 다 동의
                _report(match_key="m1", agent="rumor", pick="left"),
                _report(match_key="m1", agent="odds", pick="left", weight=0.6),
                # m2 — 셋이 답해 둘이 동의
                _report(match_key="m2", agent="rumor", pick="left"),
                _report(match_key="m2", agent="storyline", pick="left"),
                _report(match_key="m2", agent="odds", pick="right", weight=0.6),
            ],
        )
        assert [(c.answered, c.agreed, c.predictions) for c in consensus] == [
            (2, 2, 1),
            (3, 2, 1),
        ]
        # 두 줄의 confidence는 같다 — 그래서 나눠 놓아야 한다.
        assert consensus[0].confidence == consensus[1].confidence

    def test_a_level_carries_its_own_graded_denominator(self) -> None:
        _, consensus, _, _ = summarize_performance(
            [
                _prediction(match_key="m1", winner_pick="left"),
                _prediction(match_key="m2", winner_pick=None),
            ],
            [
                _report(match_key="m1", pick="left"),
                _report(match_key="m2", pick="left"),
            ],
        )
        level = consensus[0]
        assert (level.predictions, level.graded, level.correct) == (2, 1, 1)


class TestContributions:
    def test_an_agent_with_a_single_weight_value_is_constant(self) -> None:
        _, _, contributions, _ = summarize_performance(
            [_prediction(match_key=f"m{i}") for i in range(3)],
            [_report(match_key=f"m{i}", agent="rumor", weight=1.0) for i in range(3)],
        )
        rumor = contributions[0]
        assert (rumor.opinions, rumor.distinct_weights) == (3, 1)
        assert (rumor.min_weight, rumor.max_weight) == (1.0, 1.0)
        assert rumor.constant is True

    def test_an_agent_whose_weight_moves_is_not_constant(self) -> None:
        _, _, contributions, _ = summarize_performance(
            [_prediction(match_key=f"m{i}") for i in range(3)],
            [
                _report(match_key="m0", agent="odds", weight=0.5),
                _report(match_key="m1", agent="odds", weight=0.71),
                _report(match_key="m2", agent="odds", weight=0.89),
            ],
        )
        odds = contributions[0]
        assert (odds.distinct_weights, odds.constant) == (3, False)
        assert (odds.min_weight, odds.max_weight) == (0.5, 0.89)

    def test_an_agent_that_never_gave_an_opinion_is_neither_constant_nor_not(
        self,
    ) -> None:
        """상수라고 말하려면 값이 있어야 한다. 없으면 `None`이지 `False`가 아니다."""
        _, _, contributions, _ = summarize_performance(
            [_prediction()], [_report(agent="storyline", pick=None, weight=0.0)]
        )
        storyline = contributions[0]
        assert (storyline.reports, storyline.opinions) == (1, 0)
        assert storyline.distinct_weights == 0
        assert storyline.constant is None
        assert (storyline.min_weight, storyline.max_weight) == (None, None)


class TestMatchFormat:
    def test_the_pick_encoding_tells_singles_from_multi(self) -> None:
        """형식은 `pick` 값에서 나온다 — `card_json`을 읽는 새 쿼리가 필요 없다."""
        totals, _, _, _ = summarize_performance(
            [
                _prediction(match_key="m1", pick="left", winner_pick="left"),
                _prediction(match_key="m2", pick="right", winner_pick="right"),
                _prediction(match_key="m3", pick="0", winner_pick="0"),
            ],
            [],
        )
        assert (totals.singles, totals.multi) == (2, 1)
