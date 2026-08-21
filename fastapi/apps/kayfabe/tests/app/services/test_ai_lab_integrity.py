"""AI LAB 신뢰성 계산 테스트 (Phase 3-0).

이 화면에서 가장 중요한 것은 적중률이 아니라 **그 적중률을 믿어도 되는지에 대한
판정**이므로, 판정 규칙을 DB 없이 여기서 못 박는다.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from kayfabe.app.services.ai_lab_integrity import (
    CorpusFacts,
    PredictionRow,
    ReportRow,
    cites_own_event,
    summarize_agents,
    summarize_integrity,
    summarize_predictions,
    wilson_interval,
)

_NOW = datetime(2026, 8, 5, tzinfo=UTC)


def _prediction(
    *,
    slug: str = "summerslam",
    label: str = "SummerSlam",
    match_key: str = "m1",
    pick: str = "left",
    winner_pick: str | None = "left",
    source: str = "agents",
    confidence: float = 0.6,
    win_probability: float = 0.8,
) -> PredictionRow:
    return PredictionRow(
        event_slug=slug,
        event_label=label,
        match_key=match_key,
        match_title="Title Match",
        pick=pick,
        pick_name="Someone",
        win_probability=win_probability,
        confidence=confidence,
        rationale="2/2 분석이 Someone을(를) 골랐습니다.",
        source=source,
        generated_at=_NOW,
        winner_pick=winner_pick,
        winner_name="Someone",
    )


def _corpus(*, total: int = 668, published: int = 0) -> CorpusFacts:
    return CorpusFacts(
        chunks_total=total,
        chunks_embedded=total,
        chunks_with_published_at=published,
        documents=40,
        domains=1,
        last_collected_at=_NOW,
    )


class TestWilsonInterval:
    def test_no_sample_yields_no_interval(self) -> None:
        assert wilson_interval(0, 0) is None

    def test_a_perfect_record_still_opens_below_one(self) -> None:
        # 12전 12승의 점추정은 100%지만 구간은 훨씬 아래까지 열려 있다.
        low, high = wilson_interval(12, 12)
        assert low == pytest.approx(0.7575, abs=0.005)
        assert high == pytest.approx(1.0)

    def test_a_bigger_sample_narrows_the_interval(self) -> None:
        narrow = wilson_interval(100, 100)
        wide = wilson_interval(12, 12)
        assert narrow[0] > wide[0]

    def test_the_interval_stays_inside_zero_and_one(self) -> None:
        low, high = wilson_interval(0, 3)
        assert low >= 0.0
        assert high <= 1.0


class TestCitesOwnEvent:
    def test_citing_the_event_article_counts(self) -> None:
        assert cites_own_event(
            ["https://en.wikipedia.org/wiki/SummerSlam_(2026)"], "SummerSlam"
        )

    def test_citing_only_wrestler_articles_does_not(self) -> None:
        assert not cites_own_event(
            ["https://en.wikipedia.org/wiki/CM_Punk"], "SummerSlam"
        )

    def test_a_name_appearing_late_in_another_event_does_not_count(self) -> None:
        # "Champions"가 "Night of Champions" 문서에 걸리면 없는 누수를 만든다.
        assert not cites_own_event(
            ["https://en.wikipedia.org/wiki/Night_of_Champions_(2026)"], "Champions"
        )

    def test_no_sources_means_no_self_reference(self) -> None:
        assert not cites_own_event([], "SummerSlam")


class TestSummarizePredictions:
    def test_grading_excludes_the_bookmaker_fallback(self) -> None:
        rows = [
            _prediction(match_key="m1"),
            _prediction(match_key="m2", source="bookmaker_fallback"),
        ]
        totals = summarize_predictions(rows)
        assert totals.total == 2
        assert totals.graded == 1
        assert totals.bookmaker_fallback == 1

    def test_an_undecided_match_stays_out_of_the_denominator(self) -> None:
        rows = [
            _prediction(match_key="m1"),
            _prediction(match_key="m2", winner_pick=None),
        ]
        totals = summarize_predictions(rows)
        assert totals.graded == 1
        assert totals.correct == 1

    def test_hit_rate_is_none_before_anything_is_graded(self) -> None:
        totals = summarize_predictions([_prediction(winner_pick=None)])
        assert totals.hit_rate is None
        assert totals.hit_rate_low is None

    def test_a_wrong_prediction_is_counted(self) -> None:
        totals = summarize_predictions([_prediction(pick="left", winner_pick="right")])
        assert totals.correct == 0
        assert totals.incorrect == 1
        assert totals.hit_rate == 0.0

    def test_average_confidence_looks_only_at_agent_predictions(self) -> None:
        rows = [
            _prediction(match_key="m1", confidence=0.6),
            _prediction(match_key="m2", source="bookmaker_fallback", confidence=0.0),
        ]
        assert summarize_predictions(rows).avg_confidence == pytest.approx(0.6)


class TestSummarizeIntegrity:
    def test_a_prediction_citing_its_own_event_is_counted(self) -> None:
        rows = [_prediction(match_key="m1")]
        reports = [
            ReportRow(
                event_slug="summerslam",
                match_key="m1",
                agent="rumor",
                pick="left",
                weight=1.0,
                summary="자료에 따르면 ...",
                sources=("https://en.wikipedia.org/wiki/SummerSlam_(2026)",),
            )
        ]
        facts = summarize_integrity(rows, reports, _corpus(), events_total=11)
        assert facts.self_referencing_predictions == 1
        assert facts.generalizable is False
        assert any("자체를 다룬 문서" in reason for reason in facts.reasons)

    def test_without_publication_dates_time_cannot_be_verified(self) -> None:
        facts = summarize_integrity(
            [_prediction()], [], _corpus(published=0), events_total=11
        )
        assert facts.temporal_verifiable is False
        assert any("발행일" in reason for reason in facts.reasons)

    def test_with_publication_dates_time_can_be_verified(self) -> None:
        facts = summarize_integrity(
            [_prediction()], [], _corpus(published=10), events_total=11
        )
        assert facts.temporal_verifiable is True
        assert not any("발행일" in reason for reason in facts.reasons)

    def test_one_event_alone_cannot_generalize(self) -> None:
        facts = summarize_integrity(
            [_prediction()], [], _corpus(published=10), events_total=11
        )
        assert facts.events_covered == 1
        assert facts.generalizable is False
        assert any("대회 1개" in reason for reason in facts.reasons)

    def test_clearing_every_condition_reports_generalizable(self) -> None:
        rows = [
            _prediction(
                slug=f"e{i % 3}",
                label=f"Event {i % 3}",
                match_key=f"m{i}",
            )
            for i in range(30)
        ]
        facts = summarize_integrity(rows, [], _corpus(published=100), events_total=11)
        assert facts.sample_size == 30
        assert facts.events_covered == 3
        assert facts.generalizable is True
        assert facts.reasons == ()

    def test_reports_from_another_match_do_not_leak_into_citations(self) -> None:
        rows = [_prediction(match_key="m1")]
        reports = [
            ReportRow(
                event_slug="summerslam",
                match_key="other-match",
                agent="rumor",
                pick="left",
                weight=1.0,
                summary="자료에 따르면 ...",
                sources=("https://en.wikipedia.org/wiki/SummerSlam_(2026)",),
            )
        ]
        facts = summarize_integrity(rows, reports, _corpus(), events_total=11)
        assert facts.self_referencing_predictions == 0
        assert facts.predictions_with_sources == 0


class TestSummarizeAgents:
    def test_each_agent_gets_an_opinion_rate(self) -> None:
        reports = [
            ReportRow("s", "m1", "odds", "left", 0.5, "배당 근거", ()),
            ReportRow("s", "m2", "odds", None, 0.0, "배당 정보가 없습니다", ()),
            ReportRow("s", "m1", "rumor", "left", 1.0, "소식 근거", ()),
        ]
        activities = {a.agent: a for a in summarize_agents(reports)}
        assert activities["odds"].reports == 2
        assert activities["odds"].with_pick == 1
        assert activities["odds"].opinion_rate == pytest.approx(0.5)
        assert activities["rumor"].opinion_rate == pytest.approx(1.0)

    def test_no_reports_means_no_agents(self) -> None:
        assert summarize_agents([]) == []
