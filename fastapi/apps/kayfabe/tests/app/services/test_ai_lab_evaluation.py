"""평가 자격 판정 테스트 (Phase 3-6).

**이 모듈이 지키는 것은 성능이 아니라 분모다.** 자격 없는 예측이 분모에 들어가면
그 뒤의 어떤 숫자도 뜻을 잃는다.

무게 셋을 갈라 놓는 것이 테스트의 핵심이다.
- **제외**(폴백·미채점)는 실격이 아니다.
- **실격**(시간 역전·자기참조)은 누수가 확정된 것이다.
- **보류**(인용 문서가 경기보다 앞선 개정본임을 확인 못 함)는 통과도 실격도 아니다
  — **통과로 세면 판정이 무의미해진다.**

Phase 3-12에서 코퍼스 규칙의 기준이 `published_at` 존재에서 **개정본 시각 대 대회
시작일** 비교로 바뀌었다. 아래 헬퍼가 기본으로 "깨끗한 계보"를 주는 이유가 그것이다 —
이 파일의 테스트들은 대부분 코퍼스 규칙이 아니라 **다른 규칙**을 재고 있어서, 계보가
비면 재려던 것과 무관하게 전부 보류로 떨어진다. 계보 자체를 재는 테스트는
`test_ai_lab_revision_gate.py`에 따로 있다.

그리고 하나 더: **자격이 0건이면 성능 집계 함수를 호출조차 하지 않는다.**
"""

from __future__ import annotations

from datetime import UTC, date, datetime

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

#: 대회 시작일과 그보다 앞선 개정본 (Phase 3-12). 인용 문서가 경기 전 글이어야
#: 코퍼스 규칙을 지나므로, 다른 규칙을 재는 테스트들이 이 기본값을 쓴다.
_EVENT_START = date(2026, 8, 10)
_REVISED = datetime(2026, 8, 1, 7, tzinfo=UTC)

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
    event_start_date: date | None = _EVENT_START,
    match_exists: bool = True,
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
        event_start_date=event_start_date,
        match_exists=match_exists,
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


def _document(
    *,
    url: str = _DOC,
    published: int = 3,
    revisions: int = 3,
    revised_at: datetime | None = _REVISED,
) -> DocumentRow:
    return DocumentRow(
        source_url=url,
        source_domain="en.wikipedia.org",
        title="Backlash (2026)",
        chunks=3,
        chunks_embedded=3,
        chunks_with_published_at=published,
        first_published_at=None,
        last_collected_at=_BEFORE,
        chunks_with_revision=revisions,
        latest_revised_at=revised_at,
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
    def test_a_cited_document_without_a_revision_is_held(self) -> None:
        """**Phase 3-12에서 기준이 바뀌었다.** 보는 것은 개정본 시각이다.

        예전에는 `published_at`이 없으면 보류였는데, 그 값은 위키에서 늘 비어 있어
        아무것도 가르지 못했다. 이제는 우리가 읽은 개정본이 경기보다 앞선다는 것을
        확인할 수 없을 때 보류한다. 계보를 재는 나머지 경우는
        `test_ai_lab_revision_gate.py`에 있다.
        """
        item = _only(
            [_prediction()], [_report()], [_document(revisions=0, revised_at=None)]
        )
        verdict = _verdict(item, "unverifiable_corpus")
        assert verdict.failed is True
        # 실격이 아니라 보류다 — 누수를 증명도 반증도 못 한다.
        assert item.status == STATUS_HELD
        assert item.eligible is False

    def test_a_published_date_alone_does_not_pass(self) -> None:
        """발행일이 다 채워져 있어도 개정본이 없으면 통과가 아니다.

        Phase 3-11이 경고한 함정이다 — 백필만 하면 hold가 pass로 뒤집히면서
        시간 비교는 한 번도 일어나지 않는다.
        """
        item = _only(
            [_prediction()],
            [_report()],
            [_document(published=3, revisions=0, revised_at=None)],
        )
        assert item.status == STATUS_HELD

    def test_a_cited_document_missing_from_the_corpus_is_held(self) -> None:
        """코퍼스에 없는 문서는 개정본을 확인할 방법이 없다."""
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
            "withdrawn_match",
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


class TestWithdrawnMatch:
    """카드에서 사라진 경기를 가리키는 예측 (Stage 9).

    예측은 경기를 **문자열로** 가리킬 뿐 외래키가 아니다. 그래서 카드가 교체되면
    경기 행만 사라지고 예측은 남는다. 그것을 `pending`이라 부르면 거짓이다 —
    결과를 기다리는 것이 아니라 물음이 회수된 것이다.
    """

    def test_missing_match_is_withdrawn_not_pending(self) -> None:
        _, _, items, _ = summarize_evaluation(
            [_prediction(match_exists=False, winner_pick=None, finished_at=None)],
            [],
            [],
        )

        assert [i.status for i in items] == ["withdrawn_match"]

    def test_withdrawn_is_excluded_not_disqualified(self) -> None:
        """실격이 아니다 — 누수가 아니라 물음이 사라진 것이다."""
        totals, rules, _, performance = summarize_evaluation(
            [_prediction(match_exists=False, winner_pick=None, finished_at=None)],
            [],
            [],
        )
        by_code = {rule.code: rule for rule in rules}

        assert totals.withdrawn == 1
        assert totals.disqualified == 0
        assert totals.pending == 0
        assert by_code["withdrawn_match"].severity == "exclude"
        assert by_code["withdrawn_match"].blocked == 1
        assert performance is None

    def test_it_is_judged_before_pending(self) -> None:
        """경기가 없으면 `winner_pick`도 없다 — 순서가 뒤집히면 전부 pending이 된다."""
        _, _, items, _ = summarize_evaluation(
            [
                _prediction(match_key="gone", match_exists=False, winner_pick=None),
                _prediction(match_key="waiting", winner_pick=None),
            ],
            [],
            [],
        )
        by_key = {i.match_key: i.status for i in items}

        assert by_key == {"gone": "withdrawn_match", "waiting": "pending"}

    def test_declared_ex_post_still_wins(self) -> None:
        """표본의 성격은 선언이 정한다 — 경기 행의 유무보다 앞선다."""
        _, _, items, _ = summarize_evaluation(
            [
                _prediction(
                    match_exists=False,
                    winner_pick=None,
                    outcome_known_externally=True,
                    provenance_note="사후 재현",
                )
            ],
            [],
            [],
        )

        assert [i.status for i in items] == ["ex_post"]

    def test_existing_match_is_untouched(self) -> None:
        """기본값이 `True`라 기존 판정 경로가 한 줄도 바뀌지 않는다."""
        _, _, items, _ = summarize_evaluation([_prediction()], [_report()], [])

        assert [i.status for i in items] != ["withdrawn_match"]


class TestTotalsCoverEverything:
    def test_the_seven_buckets_sum_to_the_prediction_count(self) -> None:
        """일곱 칸은 겹치지 않고 전체를 덮는다 — 어디로도 새지 않는다."""
        totals, _, _, _ = summarize_evaluation(
            [
                _prediction(match_key="gone", match_exists=False, winner_pick=None),
                _prediction(match_key="waiting", winner_pick=None),
                _prediction(match_key="fallback", source="bookmaker_fallback"),
                _prediction(match_key="late", generated_at=_AFTER),
            ],
            [],
            [],
        )

        assert (
            (
                totals.fallback
                + totals.ex_post
                + totals.withdrawn
                + totals.pending
                + totals.disqualified
                + totals.held
                + totals.eligible
            )
            == totals.predictions
            == 4
        )
