"""에이전트 성적 집계 테스트 (Phase 3-3).

**분모가 셋 다 다르다.** 응답률·의견률·정확도가 각각 무엇을 나누는지가 이 화면의
전부라, 그 규칙을 DB 없이 여기서 못 박는다.

특히 셋을 구분한다.
- 의견 없음(`pick is None`)은 **오답이 아니다** — 정확도 분모에도 안 들어간다.
- 미채점(`winner_pick is None`)도 정확도 분모에서 빠진다.
- 북메이커 폴백 예측은 통째로 빠진다.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from kayfabe.app.services.ai_lab_integrity import (
    PredictionRow,
    ReportRow,
    summarize_agent_analysis,
)

_NOW = datetime(2026, 8, 5, tzinfo=UTC)


def _prediction(
    *,
    match_key: str,
    slug: str = "summerslam",
    label: str = "SummerSlam",
    winner_pick: str | None = "left",
    source: str = "agents",
) -> PredictionRow:
    return PredictionRow(
        event_slug=slug,
        event_label=label,
        match_key=match_key,
        match_title="Title Match",
        pick="left",
        pick_name="Someone",
        win_probability=0.8,
        confidence=0.6,
        rationale="…",
        source=source,
        generated_at=_NOW,
        winner_pick=winner_pick,
        winner_name="Someone",
    )


def _report(
    *,
    match_key: str,
    agent: str = "odds",
    pick: str | None = "left",
    weight: float = 0.6,
    slug: str = "summerslam",
    sources: tuple[str, ...] = (),
) -> ReportRow:
    return ReportRow(
        event_slug=slug,
        match_key=match_key,
        agent=agent,
        pick=pick,
        weight=weight,
        summary="…",
        sources=sources,
    )


def _only(agents, name: str):
    return next(a for a in agents if a.agent == name)


class TestAccuracy:
    def test_nine_of_ten_is_zero_point_nine(self) -> None:
        predictions = [_prediction(match_key=f"m{i}") for i in range(10)]
        reports = [
            _report(match_key=f"m{i}", pick="left" if i < 9 else "right")
            for i in range(10)
        ]
        _, agents = summarize_agent_analysis(predictions, reports)
        odds = _only(agents, "odds")
        assert (odds.gradable, odds.correct, odds.incorrect) == (10, 9, 1)
        assert odds.accuracy == pytest.approx(0.9)

    def test_ten_of_ten_is_one(self) -> None:
        predictions = [_prediction(match_key=f"m{i}") for i in range(10)]
        reports = [_report(match_key=f"m{i}") for i in range(10)]
        _, agents = summarize_agent_analysis(predictions, reports)
        assert _only(agents, "odds").accuracy == 1.0

    def test_zero_of_ten_is_zero(self) -> None:
        predictions = [_prediction(match_key=f"m{i}") for i in range(10)]
        reports = [_report(match_key=f"m{i}", pick="right") for i in range(10)]
        _, agents = summarize_agent_analysis(predictions, reports)
        odds = _only(agents, "odds")
        assert odds.correct == 0
        assert odds.accuracy == 0.0

    def test_nothing_gradable_leaves_accuracy_unset(self) -> None:
        predictions = [_prediction(match_key="m1", winner_pick=None)]
        reports = [_report(match_key="m1")]
        _, agents = summarize_agent_analysis(predictions, reports)
        odds = _only(agents, "odds")
        # 채점할 것이 없으면 0%가 아니라 값이 없다.
        assert odds.accuracy is None
        assert odds.accuracy_low is None


class TestNoOpinion:
    def test_no_opinion_is_not_counted_as_incorrect(self) -> None:
        predictions = [_prediction(match_key="m1"), _prediction(match_key="m2")]
        reports = [_report(match_key="m1"), _report(match_key="m2", pick=None)]
        _, agents = summarize_agent_analysis(predictions, reports)
        odds = _only(agents, "odds")
        assert odds.no_opinion == 1
        assert odds.incorrect == 0

    def test_no_opinion_stays_out_of_the_accuracy_denominator(self) -> None:
        predictions = [_prediction(match_key=f"m{i}") for i in range(4)]
        reports = [
            _report(match_key="m0"),
            _report(match_key="m1"),
            _report(match_key="m2", pick=None),
            _report(match_key="m3", pick=None),
        ]
        _, agents = summarize_agent_analysis(predictions, reports)
        odds = _only(agents, "odds")
        assert odds.reports == 4
        assert odds.with_pick == 2
        assert odds.gradable == 2
        assert odds.accuracy == 1.0

    def test_the_two_weight_averages_differ(self) -> None:
        predictions = [_prediction(match_key="m1"), _prediction(match_key="m2")]
        reports = [
            _report(match_key="m1", weight=1.0),
            _report(match_key="m2", pick=None, weight=0.0),
        ]
        _, agents = summarize_agent_analysis(predictions, reports)
        odds = _only(agents, "odds")
        # 전체 평균은 의견 없음(0.0)이 끌어내린다 — 둘을 함께 봐야 뜻이 통한다.
        assert odds.avg_weight == pytest.approx(0.5)
        assert odds.avg_weight_opinionated == pytest.approx(1.0)


class TestPending:
    def test_an_ungraded_match_leaves_the_denominator(self) -> None:
        predictions = [
            _prediction(match_key="m1"),
            _prediction(match_key="m2", winner_pick=None),
        ]
        reports = [_report(match_key="m1"), _report(match_key="m2")]
        _, agents = summarize_agent_analysis(predictions, reports)
        odds = _only(agents, "odds")
        assert odds.with_pick == 2
        assert odds.gradable == 1
        assert odds.accuracy == 1.0


class TestBookmakerFallback:
    def test_a_fallback_prediction_is_excluded_entirely(self) -> None:
        predictions = [
            _prediction(match_key="m1"),
            _prediction(match_key="m2", source="bookmaker_fallback"),
        ]
        reports = [_report(match_key="m1"), _report(match_key="m2", pick="right")]
        totals, agents = summarize_agent_analysis(predictions, reports)
        odds = _only(agents, "odds")
        # 폴백 경기의 리포트는 세지 않는다 — 응답률 분모에서도 빠진다.
        assert odds.reports == 1
        assert odds.gradable == 1
        assert odds.incorrect == 0
        assert totals.total_predictions == 1
        assert odds.response_rate == pytest.approx(1.0)


class TestRates:
    def test_response_rate_divides_by_every_prediction(self) -> None:
        predictions = [_prediction(match_key=f"m{i}") for i in range(12)]
        reports = [_report(match_key=f"m{i}", agent="storyline") for i in range(6)]
        totals, agents = summarize_agent_analysis(predictions, reports)
        storyline = _only(agents, "storyline")
        assert storyline.reports == 6
        assert totals.total_predictions == 12
        assert storyline.response_rate == pytest.approx(0.5)

    def test_opinion_rate_divides_by_that_agents_reports(self) -> None:
        predictions = [_prediction(match_key=f"m{i}") for i in range(12)]
        reports = [
            _report(
                match_key=f"m{i}", agent="storyline", pick=None if i == 5 else "left"
            )
            for i in range(6)
        ]
        _, agents = summarize_agent_analysis(predictions, reports)
        storyline = _only(agents, "storyline")
        assert storyline.opinion_rate == pytest.approx(5 / 6)

    def test_coverage_counts_distinct_matches_and_events(self) -> None:
        predictions = [
            _prediction(match_key="m1"),
            _prediction(match_key="m2"),
            _prediction(match_key="m3", slug="backlash", label="Backlash"),
        ]
        reports = [
            _report(match_key="m1"),
            _report(match_key="m2"),
            _report(match_key="m3", slug="backlash"),
        ]
        _, agents = summarize_agent_analysis(predictions, reports)
        odds = _only(agents, "odds")
        assert odds.matches_covered == 3
        assert odds.events_covered == 2


class TestWilsonReuse:
    def test_a_perfect_agent_record_does_not_collapse_to_a_point(self) -> None:
        predictions = [_prediction(match_key=f"m{i}") for i in range(10)]
        reports = [_report(match_key=f"m{i}", agent="rumor") for i in range(10)]
        _, agents = summarize_agent_analysis(predictions, reports)
        rumor = _only(agents, "rumor")
        assert rumor.accuracy == 1.0
        # 10/10이라도 구간은 아래로 열려 있다 — 표본이 작다는 사실이 숨지 않는다.
        assert rumor.accuracy_low is not None
        assert rumor.accuracy_low < 0.8
        assert rumor.accuracy_high == pytest.approx(1.0)

    def test_a_smaller_sample_opens_the_interval_wider(self) -> None:
        five = summarize_agent_analysis(
            [_prediction(match_key=f"m{i}") for i in range(5)],
            [_report(match_key=f"m{i}") for i in range(5)],
        )[1][0]
        ten = summarize_agent_analysis(
            [_prediction(match_key=f"m{i}") for i in range(10)],
            [_report(match_key=f"m{i}") for i in range(10)],
        )[1][0]
        assert five.accuracy_low < ten.accuracy_low


class TestSelfReference:
    def test_citing_the_event_article_is_counted(self) -> None:
        predictions = [_prediction(match_key="m1")]
        reports = [
            _report(
                match_key="m1",
                agent="rumor",
                sources=("https://en.wikipedia.org/wiki/SummerSlam_(2026)",),
            )
        ]
        _, agents = summarize_agent_analysis(predictions, reports)
        assert _only(agents, "rumor").self_referencing_reports == 1

    def test_a_substring_match_in_another_event_does_not_count(self) -> None:
        predictions = [_prediction(match_key="m1", slug="champions", label="Champions")]
        reports = [
            _report(
                match_key="m1",
                slug="champions",
                agent="rumor",
                sources=("https://en.wikipedia.org/wiki/Night_of_Champions_(2026)",),
            )
        ]
        _, agents = summarize_agent_analysis(predictions, reports)
        # 마지막 path segment의 접두사로만 판정한다 — 단순 포함이면 과탐이 난다.
        assert _only(agents, "rumor").self_referencing_reports == 0

    def test_an_agent_with_no_sources_does_not_use_knowledge(self) -> None:
        predictions = [_prediction(match_key="m1")]
        reports = [_report(match_key="m1", agent="odds", sources=())]
        _, agents = summarize_agent_analysis(predictions, reports)
        odds = _only(agents, "odds")
        assert odds.uses_knowledge is False
        assert odds.self_referencing_reports == 0

    def test_an_agent_with_any_source_uses_knowledge(self) -> None:
        predictions = [_prediction(match_key="m1"), _prediction(match_key="m2")]
        reports = [
            _report(match_key="m1", agent="rumor", sources=()),
            _report(
                match_key="m2",
                agent="rumor",
                sources=("https://en.wikipedia.org/wiki/CM_Punk",),
            ),
        ]
        _, agents = summarize_agent_analysis(predictions, reports)
        assert _only(agents, "rumor").uses_knowledge is True


class TestTotals:
    def test_totals_add_up_across_agents(self) -> None:
        predictions = [_prediction(match_key=f"m{i}") for i in range(3)]
        reports = [
            _report(match_key="m0", agent="odds"),
            _report(match_key="m1", agent="odds", pick=None),
            _report(match_key="m0", agent="rumor"),
            _report(match_key="m2", agent="storyline"),
        ]
        totals, agents = summarize_agent_analysis(predictions, reports)
        assert totals.agent_count == 3
        assert totals.total_reports == 4
        assert totals.opinionated == 3
        assert totals.no_opinion == 1
        assert totals.overall_opinion_rate == pytest.approx(0.75)
        assert totals.gradable_reports == 3
        assert [a.agent for a in agents] == ["odds", "rumor", "storyline"]

    def test_no_reports_yields_no_agents(self) -> None:
        totals, agents = summarize_agent_analysis([_prediction(match_key="m1")], [])
        assert agents == []
        assert totals.agent_count == 0
        # 리포트가 0건이면 의견률은 0%가 아니라 값이 없다.
        assert totals.overall_opinion_rate is None
