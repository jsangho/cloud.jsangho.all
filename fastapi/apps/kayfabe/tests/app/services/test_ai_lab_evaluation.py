"""평가 자격 판정 테스트 (Phase 3-6).

**이 모듈이 지키는 것은 성능이 아니라 분모다.** 자격 없는 예측이 분모에 들어가면
그 뒤의 어떤 숫자도 뜻을 잃는다.

무게 셋을 갈라 놓는 것이 테스트의 핵심이다.
- **제외**(폴백·미채점)는 실격이 아니다.
- **실격**(시간 역전·자기참조)은 누수가 확정된 것이다.
- **보류**(발행일 미상)는 통과도 실격도 아니다 — **통과로 세면 판정이 무의미해진다.**

그리고 하나 더: **자격이 0건이면 성능 집계 함수를 호출조차 하지 않는다.**
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from kayfabe.app.services import ai_lab_evaluation
from kayfabe.app.services.ai_lab_evaluation import (
    STATUS_DISQUALIFIED,
    STATUS_ELIGIBLE,
    STATUS_EX_POST,
    STATUS_HELD,
    STATUS_NOT_APPLICABLE,
    STATUS_PENDING,
    summarize_eligible_performance,
    summarize_evaluation,
)
from kayfabe.app.services.ai_lab_integrity import PredictionRow, ReportRow
from kayfabe.app.services.ai_lab_knowledge import DocumentRow

_RESULT_AT = datetime(2026, 8, 4, 7, tzinfo=UTC)
_BEFORE = datetime(2026, 8, 3, 7, tzinfo=UTC)
_AFTER = datetime(2026, 8, 5, 7, tzinfo=UTC)

_DOC = "https://en.wikipedia.org/wiki/Backlash_(2026)"
_OWN = "https://en.wikipedia.org/wiki/SummerSlam_(2026)"


def _prediction(
    *,
    match_key: str = "m1",
    pick: str = "left",
    winner_pick: str | None = "left",
    generated_at: datetime = _BEFORE,
    finished_at: datetime | None = _RESULT_AT,
    source: str = "agents",
    event_label: str = "SummerSlam",
    outcome_known_externally: bool | None = None,
    provenance_note: str | None = None,
) -> PredictionRow:
    return PredictionRow(
        event_slug="summerslam",
        event_label=event_label,
        match_key=match_key,
        match_title="Title Match",
        pick=pick,
        pick_name="Someone",
        win_probability=0.8,
        confidence=0.667,
        rationale="…",
        source=source,
        generated_at=generated_at,
        winner_pick=winner_pick,
        winner_name="Someone",
        finished_at=finished_at,
        outcome_known_externally=outcome_known_externally,
        provenance_note=provenance_note,
    )


def _report(*, match_key: str = "m1", sources: tuple[str, ...] = (_DOC,)) -> ReportRow:
    return ReportRow(
        event_slug="summerslam",
        match_key=match_key,
        agent="rumor",
        pick="left",
        weight=1.0,
        summary="…",
        sources=sources,
    )


def _document(*, url: str = _DOC, published: int = 3) -> DocumentRow:
    return DocumentRow(
        source_url=url,
        source_domain="en.wikipedia.org",
        title="Backlash (2026)",
        chunks=3,
        chunks_embedded=3,
        chunks_with_published_at=published,
        first_published_at=None,
        last_collected_at=_BEFORE,
    )


def _only(predictions, reports, documents):
    _, _, items, _ = summarize_evaluation(predictions, reports, documents)
    return items[0]


def _verdict(item, code: str):
    return next(v for v in item.verdicts if v.code == code)


class TestTemporalRule:
    def test_generated_after_the_result_is_disqualified(self) -> None:
        item = _only([_prediction(generated_at=_AFTER)], [_report()], [_document()])
        assert item.status == STATUS_DISQUALIFIED
        assert _verdict(item, "temporal_inversion").failed is True

    def test_generated_at_the_same_instant_is_disqualified(self) -> None:
        """같은 시각은 먼저였다고 말할 수 없다."""
        item = _only([_prediction(generated_at=_RESULT_AT)], [_report()], [_document()])
        assert item.status == STATUS_DISQUALIFIED
        assert _verdict(item, "temporal_inversion").failed is True

    def test_generated_before_the_result_passes_the_temporal_rule(self) -> None:
        item = _only([_prediction(generated_at=_BEFORE)], [_report()], [_document()])
        verdict = _verdict(item, "temporal_inversion")
        assert (verdict.failed, verdict.applicable) == (False, True)
        assert item.status == STATUS_ELIGIBLE

    def test_a_missing_result_timestamp_is_held_not_passed(self) -> None:
        """잴 수 없었던 것을 통과로 세면 이 판정이 하는 일이 없어진다."""
        item = _only([_prediction(finished_at=None)], [_report()], [_document()])
        verdict = _verdict(item, "temporal_inversion")
        assert (verdict.failed, verdict.applicable) == (False, False)
        assert item.status == STATUS_HELD
        assert item.eligible is False


class TestExclusions:
    def test_an_ungraded_prediction_is_pending_not_disqualified(self) -> None:
        item = _only(
            [_prediction(winner_pick=None, finished_at=None)],
            [_report()],
            [_document()],
        )
        assert item.status == STATUS_PENDING
        assert item.eligible is False

    def test_a_bookmaker_fallback_is_not_applicable(self) -> None:
        item = _only(
            [_prediction(source="bookmaker_fallback")], [_report()], [_document()]
        )
        assert item.status == STATUS_NOT_APPLICABLE
        # 실격이 아니다 — 애초에 에이전트의 판단이 아니었다.
        totals, _, _, _ = summarize_evaluation(
            [_prediction(source="bookmaker_fallback")], [_report()], [_document()]
        )
        assert (totals.fallback, totals.disqualified) == (1, 0)


class TestSelfReference:
    def test_citing_its_own_event_document_is_disqualified(self) -> None:
        """Phase 3-0의 규칙을 그대로 쓴다 — 새 자기참조 규칙을 만들지 않는다."""
        item = _only(
            [_prediction()],
            [_report(sources=(_OWN,))],
            [_document(url=_OWN)],
        )
        assert item.status == STATUS_DISQUALIFIED
        assert _verdict(item, "self_reference").failed is True

    def test_no_sources_is_not_assumed_to_be_self_reference(self) -> None:
        """없음을 유죄로 세지 않는다."""
        item = _only([_prediction()], [_report(sources=())], [_document()])
        verdict = _verdict(item, "self_reference")
        assert (verdict.failed, verdict.applicable) == (False, True)

    def test_a_prediction_with_no_reports_at_all_is_not_self_referencing(self) -> None:
        item = _only([_prediction()], [], [_document()])
        assert _verdict(item, "self_reference").failed is False


class TestCorpusVerifiability:
    def test_a_cited_document_without_a_published_date_is_held(self) -> None:
        item = _only([_prediction()], [_report()], [_document(published=0)])
        verdict = _verdict(item, "unverifiable_corpus")
        assert verdict.failed is True
        # 실격이 아니라 보류다 — 누수를 증명도 반증도 못 한다.
        assert item.status == STATUS_HELD
        assert item.eligible is False

    def test_a_cited_document_missing_from_the_corpus_is_held(self) -> None:
        """코퍼스에 없는 문서는 발행일을 확인할 방법이 없다."""
        item = _only(
            [_prediction()], [_report(sources=("https://gone.example/x",))], []
        )
        assert _verdict(item, "unverifiable_corpus").failed is True
        assert item.status == STATUS_HELD

    def test_it_does_not_judge_retrieval_it_has_no_record_of(self) -> None:
        """`ple_prediction_retrievals`가 없다 — 검색 청크를 사후에 추정하지 않는다.

        판정에 쓰는 것은 저장된 출처 URL까지이고, 규칙 목록에 retrieval 축이 없다.
        """
        _, rules, item, _ = summarize_evaluation(
            [_prediction()], [_report()], [_document()]
        )
        codes = {rule.code for rule in rules}
        assert not any("retriev" in code for code in codes)
        assert not any("chunk" in code or "similarity" in code for code in codes)


class TestPerformanceGate:
    def test_no_eligible_sample_yields_no_performance(self) -> None:
        totals, _, _, performance = summarize_evaluation(
            [_prediction(generated_at=_AFTER)], [_report()], [_document()]
        )
        assert totals.eligible == 0
        # 0%도 빈 객체도 아니다.
        assert performance is None

    def test_the_aggregator_is_not_even_called_without_an_eligible_sample(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """0건짜리 비율을 만들 기회 자체를 없앤다."""
        calls: list[int] = []

        def _spy(rows):
            calls.append(len(rows))
            raise AssertionError("자격 0건인데 성능 집계가 불렸다")

        monkeypatch.setattr(ai_lab_evaluation, "summarize_eligible_performance", _spy)
        summarize_evaluation(
            [_prediction(generated_at=_AFTER)], [_report()], [_document()]
        )
        assert calls == []

    def test_an_eligible_sample_produces_numbers_with_an_interval(self) -> None:
        rows = [
            _prediction(match_key="m1", pick="left", winner_pick="left"),
            _prediction(match_key="m2", pick="left", winner_pick="right"),
        ]
        reports = [_report(match_key="m1"), _report(match_key="m2")]
        totals, _, _, performance = summarize_evaluation(rows, reports, [_document()])
        assert totals.eligible == 2
        assert performance is not None
        assert (performance.sample, performance.correct, performance.incorrect) == (
            2,
            1,
            1,
        )
        assert performance.accuracy == 0.5
        # 표본이 작아도 숫자는 낸다 — 대신 구간을 함께 낸다(3-0 규칙).
        assert performance.accuracy_low < 0.5 < performance.accuracy_high

    def test_the_aggregator_refuses_an_empty_sample(self) -> None:
        with pytest.raises(ValueError):
            summarize_eligible_performance([])


class TestProvenanceRule:
    """Phase 3-7. **선언하지 않은 예측의 판정은 한 글자도 바뀌지 않아야 한다.**

    이 축이 하는 일은 시간 규칙이 볼 수 없는 것 — 결과가 시스템 **밖에서** 이미
    알려져 있었는가 — 을 적는 것이다. 시간 규칙을 대신하지 않고 옆에 선다.
    """

    def test_declaring_external_knowledge_is_ex_post_not_disqualified(self) -> None:
        item = _only(
            [_prediction(outcome_known_externally=True)], [_report()], [_document()]
        )
        assert item.status == STATUS_EX_POST
        assert item.eligible is False
        # 실격과 섞지 않는다 — 누수 확정과 표본 성격은 다른 사실이다.
        assert item.status != STATUS_DISQUALIFIED

    def test_an_undeclared_prediction_keeps_its_original_verdicts(self) -> None:
        """`None`은 모른다가 아니라 **선언되지 않았다**는 뜻이다."""
        declared_none = _only([_prediction()], [_report()], [_document()])
        declared_false = _only(
            [_prediction(outcome_known_externally=False)], [_report()], [_document()]
        )
        assert declared_none.status == STATUS_ELIGIBLE
        assert declared_false.status == STATUS_ELIGIBLE
        # 규칙 코드도 사유 문장도 그대로다.
        assert [
            (v.code, v.failed, v.applicable, v.detail) for v in declared_none.verdicts
        ] == [
            (v.code, v.failed, v.applicable, v.detail) for v in declared_false.verdicts
        ]

    def test_it_does_not_catch_none_as_a_falsy_value(self) -> None:
        """`is True`가 아니라 truthy로 봤다면 여기서 무너진다."""
        item = _only(
            [_prediction(match_key="late", generated_at=_AFTER)],
            [_report(match_key="late")],
            [_document()],
        )
        assert item.status == STATUS_DISQUALIFIED
        assert _verdict(item, "temporal_inversion").failed is True

    def test_an_ex_post_sample_is_not_judged_by_the_temporal_rule(self) -> None:
        item = _only(
            [_prediction(outcome_known_externally=True, generated_at=_AFTER)],
            [_report()],
            [_document()],
        )
        assert [v.code for v in item.verdicts] == ["external_outcome_known"]

    def test_it_stays_ex_post_even_before_a_result_exists(self) -> None:
        """결과가 없어 `pending`으로 보일 수 있어도 채점 대상이 되지 못한다."""
        item = _only(
            [
                _prediction(
                    winner_pick=None, finished_at=None, outcome_known_externally=True
                )
            ],
            [_report()],
            [_document()],
        )
        assert item.status == STATUS_EX_POST

    def test_a_bookmaker_fallback_is_judged_before_provenance(self) -> None:
        item = _only(
            [_prediction(source="bookmaker_fallback", outcome_known_externally=True)],
            [_report()],
            [_document()],
        )
        assert item.status == STATUS_NOT_APPLICABLE

    def test_an_ex_post_sample_never_reaches_the_performance_denominator(self) -> None:
        totals, _, _, performance = summarize_evaluation(
            [_prediction(match_key="expost", outcome_known_externally=True)],
            [_report(match_key="expost")],
            [_document()],
        )
        assert (totals.ex_post, totals.eligible) == (1, 0)
        assert performance is None

    def test_the_declared_note_is_the_reason_shown(self) -> None:
        """사유는 사람이 쓴 문장 그대로다 — 모듈이 지어내지 않는다."""
        note = "Historical/ex-post sample. Match had already occurred."
        item = _only(
            [_prediction(outcome_known_externally=True, provenance_note=note)],
            [_report()],
            [_document()],
        )
        assert _verdict(item, "external_outcome_known").detail == note

    def test_the_rule_is_an_exclusion_not_a_disqualification(self) -> None:
        _, rules, _, _ = summarize_evaluation(
            [_prediction(outcome_known_externally=True)], [_report()], [_document()]
        )
        rule = next(r for r in rules if r.code == "external_outcome_known")
        assert rule.severity == "exclude"
        assert rule.blocked == 1


class TestTotals:
    def test_the_six_buckets_cover_every_prediction(self) -> None:
        totals, _, _, _ = summarize_evaluation(
            [
                _prediction(match_key="ok"),
                _prediction(match_key="late", generated_at=_AFTER),
                _prediction(match_key="pending", winner_pick=None, finished_at=None),
                _prediction(match_key="fb", source="bookmaker_fallback"),
                _prediction(match_key="unknown", finished_at=None),
                _prediction(match_key="expost", outcome_known_externally=True),
            ],
            [
                _report(match_key=key)
                for key in ("ok", "late", "pending", "fb", "unknown", "expost")
            ],
            [_document()],
        )
        assert totals.predictions == 6
        assert (totals.eligible, totals.disqualified) == (1, 1)
        assert (totals.pending, totals.fallback, totals.held) == (1, 1, 1)
        assert totals.ex_post == 1
        # 어디로도 새지 않는다.
        assert (
            totals.eligible
            + totals.disqualified
            + totals.pending
            + totals.fallback
            + totals.held
            + totals.ex_post
            == totals.predictions
        )

    def test_no_predictions_is_an_ordinary_empty_result(self) -> None:
        totals, rules, items, performance = summarize_evaluation([], [], [])
        assert totals.predictions == 0
        assert (items, performance) == ([], None)
        # 규칙 목록은 고정이다 — 예측이 없어도 자리를 지운다.
        assert [rule.code for rule in rules] == [
            "not_applicable",
            "external_outcome_known",
            "pending",
            "temporal_inversion",
            "self_reference",
            "unverifiable_corpus",
        ]

    def test_each_rule_reports_how_many_it_blocked(self) -> None:
        _, rules, _, _ = summarize_evaluation(
            [
                _prediction(match_key="late", generated_at=_AFTER),
                _prediction(match_key="own"),
            ],
            [_report(match_key="late"), _report(match_key="own", sources=(_OWN,))],
            [_document(), _document(url=_OWN)],
        )
        by_code = {rule.code: rule for rule in rules}
        assert by_code["temporal_inversion"].blocked == 1
        assert by_code["self_reference"].blocked == 1
        assert by_code["temporal_inversion"].severity == "disqualify"
        assert by_code["unverifiable_corpus"].severity == "hold"
