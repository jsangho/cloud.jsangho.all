"""채점 모집단 계약 테스트 (Phase 3-7 후속).

3-6·3-7은 **자격 없는 예측을 분모에서 빼는 것**을 원칙으로 세웠는데, 그 원칙이
`summarize_evaluation` 안에서만 지켜지고 있었다. 나머지 네 집계 함수는
`outcome_known_externally`를 한 번도 보지 않아, 자격 판정이 "채점 대상 아님"이라고
적은 표본이 공개 적중률의 분모로 되돌아왔다.

여기서 못 박는 계약은 하나다.

    "무엇을 했는가"(활동량·재고)와 "무엇으로 점수를 매기는가"(채점 표본)는
    분모가 다르다.

**가장 중요한 테스트는 `TestExPostStaysOutOfScoring.test_a_filled_in_result_...`다.**
사후 재현 표본에 결과를 입력해도 적중률이 움직이지 않아야 한다 — 그게 안 되면
Bad Blood·King & Queen 7건의 결과를 넣는 순간 공개 지표가 오염된다.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from kayfabe.app.services.ai_lab_evaluation import summarize_evaluation
from kayfabe.app.services.ai_lab_integrity import (
    BOOKMAKER_FALLBACK,
    CorpusFacts,
    PredictionRow,
    ReportRow,
    is_scorable,
    summarize_agent_analysis,
    summarize_integrity,
    summarize_predictions,
)
from kayfabe.app.services.ai_lab_knowledge import DocumentRow
from kayfabe.app.services.ai_lab_performance import summarize_performance

_GENERATED = datetime(2026, 8, 24, tzinfo=UTC)
#: 결과가 예측보다 **나중에** 기록된 시각. 시간 규칙을 통과하는 자리다.
_RECORDED = datetime(2026, 8, 25, tzinfo=UTC)


def _prediction(
    *,
    slug: str = "summerslam",
    label: str = "SummerSlam",
    match_key: str = "m1",
    pick: str = "left",
    winner_pick: str | None = "left",
    finished_at: datetime | None = _RECORDED,
    source: str = "agents",
    outcome_known_externally: bool | None = None,
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
        rationale="근거 문장.",
        source=source,
        generated_at=_GENERATED,
        winner_pick=winner_pick,
        winner_name="Someone" if winner_pick else None,
        finished_at=finished_at,
        outcome_known_externally=outcome_known_externally,
        provenance_note="사후 재현 표본." if outcome_known_externally else None,
    )


def _ex_post(**kwargs) -> PredictionRow:
    """운영의 7건과 같은 모양 — 선언은 있고 결과는 아직 없다."""
    kwargs.setdefault("slug", "bad-blood")
    kwargs.setdefault("label", "Bad Blood")
    kwargs.setdefault("winner_pick", None)
    kwargs.setdefault("finished_at", None)
    return _prediction(outcome_known_externally=True, **kwargs)


def _report(
    *,
    slug: str = "summerslam",
    match_key: str = "m1",
    agent: str = "odds",
    pick: str | None = "left",
    weight: float = 0.6,
    sources: tuple[str, ...] = (),
) -> ReportRow:
    return ReportRow(
        event_slug=slug,
        match_key=match_key,
        agent=agent,
        pick=pick,
        weight=weight,
        summary="요약.",
        sources=sources,
    )


def _corpus(*, total: int = 668, published: int = 0) -> CorpusFacts:
    return CorpusFacts(
        chunks_total=total,
        chunks_embedded=total,
        chunks_with_published_at=published,
        documents=31,
        domains=1,
        last_collected_at=_GENERATED,
    )


class TestIsScorable:
    """공유 술어. **네 함수가 이 정의 하나만 본다.**"""

    def test_an_ordinary_prediction_is_scorable(self) -> None:
        # CASE C — 선언되지 않은(`None`) 예측은 정상 채점 표본이다.
        assert is_scorable(_prediction()) is True

    def test_a_bookmaker_fallback_is_not_scorable(self) -> None:
        assert is_scorable(_prediction(source=BOOKMAKER_FALLBACK)) is False

    def test_a_declared_ex_post_sample_is_not_scorable(self) -> None:
        assert is_scorable(_ex_post()) is False

    def test_none_means_undeclared_not_unknown(self) -> None:
        """**`is not True`여야 하는 이유를 값으로 못 박는다.**

        `not row.outcome_known_externally`로 썼다면 `None`도 `False`도 함께 걸려
        정상 표본이 채점에서 빠진다. `None`은 아무도 선언하지 않았다는 뜻이고,
        `False`는 "결과가 밖에 알려지지 않았다"고 **명시한** 것이다 — 둘 다 채점한다.
        """
        assert is_scorable(_prediction(outcome_known_externally=None)) is True
        assert is_scorable(_prediction(outcome_known_externally=False)) is True


class TestExPostStaysOutOfScoring:
    """CASE A·B — 결과 입력 전에도, 입력 후에도 채점 분모 밖이다."""

    def test_an_ungraded_ex_post_sample_is_not_counted(self) -> None:
        # CASE A — 운영 현재 상태. `winner_pick`이 없어서가 아니라
        # **선언됐기 때문에** 빠진다는 것을 아래 테스트가 가른다.
        totals = summarize_predictions([_prediction(), _ex_post(match_key="bb1")])
        assert totals.total == 2
        assert totals.graded == 1
        assert totals.correct == 1

    def test_a_filled_in_result_does_not_move_the_hit_rate(self) -> None:
        """**이 파일에서 가장 중요한 테스트다.**

        Bad Blood·King & Queen 7건에 실제 결과를 넣어도 공개 적중률이 움직이면
        안 된다. 예전 코드는 `winner_pick is not None`만 봤기 때문에 결과를 넣는
        순간 사후 재현 표본이 분모로 들어왔다.
        """
        before = summarize_predictions([_prediction(), _ex_post(match_key="bb1")])
        after = summarize_predictions(
            [
                _prediction(),
                # 결과가 들어왔다 — 그래도 채점하지 않는다.
                _ex_post(match_key="bb1", winner_pick="left", finished_at=_RECORDED),
            ]
        )
        assert after.graded == before.graded == 1
        assert after.correct == before.correct == 1
        assert after.hit_rate == before.hit_rate == 1.0

    def test_a_wrong_ex_post_sample_cannot_drag_the_hit_rate_down(self) -> None:
        # 승패와 무관해야 한다 — 오답이어도 분모에 없다.
        totals = summarize_predictions(
            [
                _prediction(),
                _ex_post(
                    match_key="bb1",
                    pick="left",
                    winner_pick="right",
                    finished_at=_RECORDED,
                ),
            ]
        )
        assert totals.graded == 1
        assert totals.correct == 1
        assert totals.hit_rate == 1.0

    def test_averages_use_the_scoring_population(self) -> None:
        """평균 둘도 채점 모집단을 쓴다.

        사후 재현 표본은 근거 문서가 없어 확신도가 낮게 깔린다. 그 값이 채점 대상
        예측의 평균 확신도인 척하면 화면이 실제보다 자신 없어 보인다.
        """
        totals = summarize_predictions(
            [
                _prediction(confidence=0.9, win_probability=0.9),
                _ex_post(match_key="bb1", confidence=0.1, win_probability=0.1),
            ]
        )
        assert totals.avg_confidence == pytest.approx(0.9)
        assert totals.avg_win_probability == pytest.approx(0.9)


class TestFallbackResidualSurvives:
    """CASE D — 잔차식이 새 필터에 오염되지 않는다."""

    def test_an_ex_post_sample_is_never_counted_as_a_fallback(self) -> None:
        """**잔차식을 제자리에서 좁혔다면 여기서 깨진다.**

        `bookmaker_fallback`은 `len(rows) - len(agent_rows)`로 계산된다. 만약
        `agent_rows`에 사후 재현 필터를 더했다면 폴백이 아닌 이유로 빠진 예측이
        폴백으로 집계된다 — 운영 데이터라면 0건이 7건으로 보고된다.
        """
        totals = summarize_predictions(
            [_prediction(), _ex_post(match_key="bb1"), _ex_post(match_key="bb2")]
        )
        assert totals.bookmaker_fallback == 0

    def test_a_real_fallback_is_still_counted(self) -> None:
        totals = summarize_predictions(
            [
                _prediction(),
                _prediction(match_key="m2", source=BOOKMAKER_FALLBACK),
                _ex_post(match_key="bb1"),
            ]
        )
        assert totals.bookmaker_fallback == 1
        assert totals.graded == 1

    def test_performance_keeps_its_own_residual_intact(self) -> None:
        totals, _levels, _contrib, _items = summarize_performance(
            [_prediction(), _ex_post(match_key="bb1")], []
        )
        assert totals.bookmaker_fallback == 0
        assert totals.predictions == 2


class TestIntegritySharesOnePopulation:
    """CASE E — `sample_size`와 `events_covered`가 같은 모집단을 본다."""

    def test_events_covered_counts_only_the_scored_sample(self) -> None:
        """운영 구조를 그대로 재현한다.

        채점된 표본은 SummerSlam 한 대회에만 있고, 나머지 두 대회에는 사후 재현
        표본만 있다. 예전 코드는 미채점 예측까지 세어 `events_covered=3`을 냈고,
        그 값이 `MIN_EVENTS_FOR_GENERALIZATION=2`를 통과해 **경고 하나를 통째로
        삼켰다.**
        """
        rows = [
            _prediction(match_key="m1"),
            _prediction(match_key="m2"),
            _ex_post(slug="bad-blood", label="Bad Blood", match_key="bb1"),
            _ex_post(
                slug="king-queen-of-the-ring",
                label="King & Queen of the Ring",
                match_key="kq1",
            ),
        ]
        facts = summarize_integrity(rows, [], _corpus(), events_total=11)

        assert facts.sample_size == 2
        assert facts.events_covered == 1
        assert any("대회 1개" in reason for reason in facts.reasons)
        assert facts.generalizable is False

    def test_an_ungraded_ordinary_prediction_also_stays_out(self) -> None:
        """이 교정은 사후 재현과 **독립이다.**

        아직 결과가 안 나온 평범한 예측도 적중률을 만들지 않았으므로 그 대회를
        커버리지로 세면 안 된다.
        """
        rows = [
            _prediction(match_key="m1"),
            _prediction(
                slug="backlash", label="Backlash", match_key="b1", winner_pick=None
            ),
        ]
        facts = summarize_integrity(rows, [], _corpus(), events_total=11)

        assert facts.sample_size == 1
        assert facts.events_covered == 1

    def test_corpus_facts_are_untouched(self) -> None:
        facts = summarize_integrity(
            [_prediction(), _ex_post(match_key="bb1")],
            [],
            _corpus(total=668, published=0),
            events_total=11,
        )
        assert facts.chunks_total == 668
        assert facts.chunks_with_published_at == 0
        assert facts.temporal_verifiable is False


class TestAgentAccuracyVersusActivity:
    """CASE B·G — 정확도만 좁히고 활동량은 그대로 둔다."""

    @staticmethod
    def _fixture() -> tuple[list[PredictionRow], list[ReportRow]]:
        predictions = [
            _prediction(match_key="m1"),
            # 결과까지 들어온 사후 재현 표본 — 정확도에는 못 들어간다.
            _ex_post(
                slug="bad-blood",
                label="Bad Blood",
                match_key="bb1",
                pick="left",
                winner_pick="right",
                finished_at=_RECORDED,
            ),
        ]
        reports = [
            _report(match_key="m1", agent="odds", pick="left"),
            _report(slug="bad-blood", match_key="bb1", agent="odds", pick="left"),
        ]
        return predictions, reports

    def test_accuracy_ignores_the_ex_post_report(self) -> None:
        predictions, reports = self._fixture()
        totals, agents = summarize_agent_analysis(predictions, reports)
        odds = next(a for a in agents if a.agent == "odds")

        # 사후 재현 표본에서 odds는 틀렸지만(left vs right) 정확도가 내려가지 않는다.
        assert odds.gradable == 1
        assert odds.correct == 1
        assert odds.accuracy == 1.0
        assert totals.gradable_reports == 1

    def test_activity_still_counts_the_ex_post_work(self) -> None:
        """CASE G — 에이전트는 실제로 답했다. 그 사실은 지우지 않는다."""
        predictions, reports = self._fixture()
        totals, agents = summarize_agent_analysis(predictions, reports)
        odds = next(a for a in agents if a.agent == "odds")

        assert totals.total_reports == 2
        assert totals.opinionated == 2
        assert totals.total_predictions == 2
        assert odds.reports == 2
        assert odds.with_pick == 2
        assert odds.no_opinion == 0
        assert odds.opinion_rate == 1.0
        assert odds.response_rate == 1.0


class TestPerformanceInventoryVersusScoring:
    """CASE B·G — Synthesis 화면의 재고는 남고 채점만 좁아진다."""

    @staticmethod
    def _rows() -> list[PredictionRow]:
        return [
            _prediction(match_key="m1"),
            _ex_post(
                slug="bad-blood",
                label="Bad Blood",
                match_key="bb1",
                pick="left",
                winner_pick="right",
                finished_at=_RECORDED,
            ),
        ]

    def test_scoring_excludes_the_ex_post_sample(self) -> None:
        totals, _levels, _contrib, _items = summarize_performance(self._rows(), [])
        assert totals.graded == 1
        assert totals.correct == 1
        assert totals.incorrect == 0

    def test_inventory_keeps_the_ex_post_sample(self) -> None:
        # CASE G — 재고 수치는 "무엇이 있었는가"라서 줄면 안 된다.
        totals, _levels, _contrib, _items = summarize_performance(self._rows(), [])
        assert totals.predictions == 2
        assert totals.singles == 2
        assert totals.multi == 0

    def test_consensus_levels_keep_stock_but_not_score(self) -> None:
        """합의 버킷도 `graded`/`correct`를 **따로** 세므로 여기에도 필터가 필요하다."""
        reports = [
            _report(match_key="m1", agent="odds", pick="left"),
            _report(slug="bad-blood", match_key="bb1", agent="odds", pick="left"),
        ]
        _totals, levels, _contrib, _items = summarize_performance(self._rows(), reports)

        # 둘 다 (answered=1, agreed=1)이라 한 버킷에 모인다.
        assert len(levels) == 1
        level = levels[0]
        assert level.predictions == 2  # 재고는 둘
        assert level.graded == 1  # 채점은 하나
        assert level.correct == 1

    def test_contributions_count_every_report(self) -> None:
        reports = [
            _report(match_key="m1", agent="odds", pick="left"),
            _report(slug="bad-blood", match_key="bb1", agent="odds", pick="left"),
        ]
        _totals, _levels, contributions, _items = summarize_performance(
            self._rows(), reports
        )
        assert sum(c.reports for c in contributions) == 2


class TestEvaluationIsUntouched:
    """CASE F — 자격 판정은 이 변경을 모른다."""

    @staticmethod
    def _documents() -> list[DocumentRow]:
        return [
            DocumentRow(
                source_url="https://en.wikipedia.org/wiki/Liv_Morgan",
                source_domain="en.wikipedia.org",
                title="Liv Morgan",
                chunks=25,
                chunks_embedded=25,
                chunks_with_published_at=0,
                first_published_at=None,
                last_collected_at=_GENERATED,
            )
        ]

    def test_an_ex_post_sample_is_classified_before_the_result_is_read(self) -> None:
        """결과를 넣어도 `ex_post` 그대로다 — `_judge()`가 그 전에 끝내기 때문이다."""
        without_result = [_prediction(), _ex_post(match_key="bb1")]
        with_result = [
            _prediction(),
            _ex_post(match_key="bb1", winner_pick="left", finished_at=_RECORDED),
        ]

        before, before_rules, _items, before_perf = summarize_evaluation(
            without_result, [], self._documents()
        )
        after, after_rules, _items2, after_perf = summarize_evaluation(
            with_result, [], self._documents()
        )

        assert after == before
        assert after_rules == before_rules
        # 자격 있는 표본은 정상 예측 한 건뿐이고, 결과 입력이 그 값을 흔들지 않는다.
        assert after_perf == before_perf
        assert after.ex_post == before.ex_post == 1

    def test_the_buckets_still_cover_every_prediction(self) -> None:
        rows = [_prediction(), _ex_post(match_key="bb1"), _ex_post(match_key="bb2")]
        totals, _rules, _items, performance = summarize_evaluation(
            rows, [], self._documents()
        )

        assert totals.ex_post == 2
        assert totals.eligible == 1
        assert performance is not None
        assert (
            totals.fallback
            + totals.ex_post
            + totals.pending
            + totals.disqualified
            + totals.held
            + totals.eligible
            == totals.predictions
        )

    def test_an_undeclared_prediction_keeps_its_old_verdict(self) -> None:
        """기존 12건이 지나는 길이다 — `None`은 판정 경로를 그대로 통과한다."""
        # 결과 기록보다 나중에 생성된 예측은 예전처럼 실격이다.
        rows = [_prediction(finished_at=_GENERATED)]
        totals, _rules, items, _perf = summarize_evaluation(rows, [], self._documents())

        assert totals.disqualified == 1
        assert items[0].status == "disqualified"
        assert any(
            v.code == "temporal_inversion" and v.failed for v in items[0].verdicts
        )
