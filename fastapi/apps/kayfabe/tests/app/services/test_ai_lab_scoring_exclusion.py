"""개별 예측 줄이 채점 제외를 드러낸다 (Phase 3-8 잔여).

3-8·3-9가 닫은 것은 **집계**다. 사후 재현 표본은 적중률의 분모에서 빠졌다.
그런데 같은 화면의 **개별 예측 줄**은 그 구분을 하지 않는다 — `correct`만 내므로
결과가 들어가는 순간 그 줄에 정답 표시가 붙고, 같은 화면 위쪽 적중률은 그것을
세지 않는다. 숫자는 맞는데 화면이 스스로 모순된다.

지금은 안 드러난다. 운영 7건이 `winner_pick=NULL`이라 `correct`가 전부 `None`이기
때문이다. **결과를 입력하는 순간 드러나므로, 입력보다 먼저 닫는다.**

여기서 못 박는 것은 셋이다.

1. `scoring_exclusion`과 `is_scorable`은 **같은 규칙**이다 — 한쪽만 바뀔 수 없다.
2. `correct`를 지우지 않는다. "맞혔는가"와 "적중률에 세는가"는 다른 질문이다.
3. 결과를 넣어도 **집계는 안 움직이고**, 그 줄은 제외 사유를 단다.

실행:

    cd fastapi
    PYTHONUTF8=1 PYTHONPATH=apps uv run pytest apps/kayfabe/tests/app/services/test_ai_lab_scoring_exclusion.py -q
"""

from __future__ import annotations

from datetime import UTC, datetime

from kayfabe.app.dtos.ai_lab_dto import RecentPrediction
from kayfabe.app.services.ai_lab_integrity import (
    BOOKMAKER_FALLBACK,
    EXCLUDED_BOOKMAKER_FALLBACK,
    EXCLUDED_EX_POST,
    PredictionRow,
    ReportRow,
    is_scorable,
    scoring_exclusion,
    summarize_predictions,
)
from kayfabe.app.services.ai_lab_performance import summarize_performance

_GENERATED = datetime(2026, 8, 24, tzinfo=UTC)
_RECORDED = datetime(2026, 8, 25, tzinfo=UTC)


def _prediction(
    *,
    match_key: str = "m1",
    pick: str = "left",
    winner_pick: str | None = "left",
    source: str = "agents",
    outcome_known_externally: bool | None = None,
) -> PredictionRow:
    return PredictionRow(
        event_slug="summerslam",
        event_label="SummerSlam",
        match_key=match_key,
        match_title="Title Match",
        pick=pick,
        pick_name="Someone",
        win_probability=0.8,
        confidence=0.6,
        rationale="근거 문장.",
        source=source,
        generated_at=_GENERATED,
        winner_pick=winner_pick,
        winner_name="Someone" if winner_pick else None,
        finished_at=_RECORDED if winner_pick else None,
        outcome_known_externally=outcome_known_externally,
        provenance_note="사후 재현 표본." if outcome_known_externally else None,
    )


def _report(*, match_key: str = "m1", pick: str | None = "left") -> ReportRow:
    return ReportRow(
        event_slug="summerslam",
        match_key=match_key,
        agent="odds",
        pick=pick,
        weight=0.6,
        summary="요약.",
        sources=(),
    )


class TestOneRuleTwoViews:
    """**두 함수가 서로 어긋나면 화면과 집계가 갈린다.**"""

    def test_an_ordinary_prediction_has_no_exclusion(self) -> None:
        row = _prediction()

        assert scoring_exclusion(row) is None
        assert is_scorable(row)

    def test_a_declared_sample_is_excluded_as_ex_post(self) -> None:
        row = _prediction(outcome_known_externally=True)

        assert scoring_exclusion(row) == EXCLUDED_EX_POST
        assert not is_scorable(row)

    def test_a_fallback_is_excluded_as_fallback(self) -> None:
        row = _prediction(source=BOOKMAKER_FALLBACK)

        assert scoring_exclusion(row) == EXCLUDED_BOOKMAKER_FALLBACK
        assert not is_scorable(row)

    def test_an_undeclared_sample_is_not_excluded(self) -> None:
        """**`None`은 "모른다"가 아니라 "선언되지 않았다"다.**

        여기서 미끄러지면 선언한 적 없는 기존 12건이 통째로 제외 표시를 단다.
        """
        row = _prediction(outcome_known_externally=None)

        assert scoring_exclusion(row) is None
        assert is_scorable(row)

    def test_an_explicit_false_is_not_excluded(self) -> None:
        row = _prediction(outcome_known_externally=False)

        assert scoring_exclusion(row) is None
        assert is_scorable(row)

    def test_fallback_wins_when_both_apply(self) -> None:
        """에이전트가 답을 못 낸 쪽이 더 앞선 사실이다 — `is_scorable`의 순서와 같다."""
        row = _prediction(source=BOOKMAKER_FALLBACK, outcome_known_externally=True)

        assert scoring_exclusion(row) == EXCLUDED_BOOKMAKER_FALLBACK

    def test_the_two_never_disagree(self) -> None:
        shapes = [
            _prediction(),
            _prediction(outcome_known_externally=True),
            _prediction(outcome_known_externally=False),
            _prediction(source=BOOKMAKER_FALLBACK),
            _prediction(source=BOOKMAKER_FALLBACK, outcome_known_externally=True),
            _prediction(winner_pick=None),
        ]

        for row in shapes:
            assert is_scorable(row) == (scoring_exclusion(row) is None)


class TestPerformanceItemsCarryTheReason:
    def test_an_ordinary_item_carries_no_reason(self) -> None:
        _, _, _, items = summarize_performance([_prediction()], [_report()])

        assert [i.scoring_exclusion for i in items] == [None]

    def test_an_ex_post_item_says_why_it_is_not_counted(self) -> None:
        _, _, _, items = summarize_performance(
            [_prediction(outcome_known_externally=True)], [_report()]
        )

        assert [i.scoring_exclusion for i in items] == [EXCLUDED_EX_POST]

    def test_a_filled_in_result_shows_on_the_row_but_not_in_the_totals(self) -> None:
        """**이 테스트가 이 파일의 이유다.**

        사후 재현 표본에 결과가 들어가면 그 줄은 정답을 말해야 하고(사실이다),
        적중률은 움직이지 않아야 한다(3-8). 둘이 함께 성립하려면 줄이 **왜**
        안 세어지는지를 들고 있어야 한다.
        """
        rows = [
            _prediction(match_key="scored"),
            _prediction(
                match_key="replayed", winner_pick="left", outcome_known_externally=True
            ),
        ]
        reports = [_report(match_key="scored"), _report(match_key="replayed")]

        totals, _, _, items = summarize_performance(rows, reports)
        replayed = next(i for i in items if i.match_key == "replayed")

        assert totals.graded == 1
        assert totals.correct == 1
        # 맞힌 사실은 지우지 않는다 — 지우면 그 표본이 무엇을 했는지 사라진다.
        assert replayed.correct is True
        assert replayed.scoring_exclusion == EXCLUDED_EX_POST

    def test_the_totals_do_not_move_when_a_replay_result_lands(self) -> None:
        """3-8의 계약을 개별 줄 쪽에서 다시 확인한다."""
        before = summarize_performance(
            [
                _prediction(match_key="scored"),
                _prediction(
                    match_key="replayed",
                    winner_pick=None,
                    outcome_known_externally=True,
                ),
            ],
            [_report(match_key="scored"), _report(match_key="replayed")],
        )[0]
        after = summarize_performance(
            [
                _prediction(match_key="scored"),
                _prediction(
                    match_key="replayed",
                    winner_pick="left",
                    outcome_known_externally=True,
                ),
            ],
            [_report(match_key="scored"), _report(match_key="replayed")],
        )[0]

        assert (before.graded, before.correct) == (after.graded, after.correct)


class TestRecentCarriesTheReason:
    """개요의 최근 목록은 **재고**라 폴백까지 싣는다 — 그래서 이유가 둘이다."""

    def test_a_recent_row_defaults_to_no_reason(self) -> None:
        """기존 호출자를 깨지 않는 기본값이다."""
        row = RecentPrediction(
            event_slug="summerslam",
            event_label="SummerSlam",
            match_key="m1",
            match_title="Title Match",
            pick_name="Someone",
            win_probability=0.8,
            confidence=0.6,
            source="agents",
            generated_at=_GENERATED,
            winner_name="Someone",
            correct=True,
        )

        assert row.scoring_exclusion is None


class TestTheAggregatesAreUntouched:
    """**이 변경은 보고만 늘린다.** 분모는 3-8·3-9가 정한 그대로다."""

    def test_the_hit_rate_ignores_both_kinds_of_excluded_rows(self) -> None:
        totals = summarize_predictions(
            [
                _prediction(match_key="scored"),
                _prediction(match_key="replayed", outcome_known_externally=True),
                _prediction(match_key="fallback", source=BOOKMAKER_FALLBACK),
            ]
        )

        assert totals.total == 3
        assert totals.graded == 1
        assert totals.correct == 1
        assert totals.bookmaker_fallback == 1
