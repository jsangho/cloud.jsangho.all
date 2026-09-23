"""누수 그래프 (Phase 10).

**이 그래프가 지키는 것은 원인의 정직함이다.** "실격 12건"은 이미 보이는데, 무엇
때문에 12건인지가 문서 단위로 없었다. 그 간선을 만들면서 틀리기 쉬운 자리가 셋이다.

1. **판정을 다시 하면 안 된다** — 상태는 평가 화면이 낸 것을 그대로 쓴다.
2. **원인이 여럿일 때 아무도 원인이 아니게 되면 안 된다** — 대회 문서를 둘 인용했으면
   어느 쪽을 빼도 자기참조는 남는다. 반사실만 쓰면 둘 다 무죄가 되므로, 기여는
   규칙이 쓰는 **같은 프리미티브**로 직접 읽는다.
3. **합이 맞아야 한다** — 시간 역전처럼 문서로 돌릴 수 없는 이유가 있고, 그 수를
   따로 세지 않으면 그래프가 "전부 문서 탓"이라고 말하게 된다.

실행:

    cd fastapi
    PYTHONUTF8=1 PYTHONPATH=apps uv run pytest \\
        apps/kayfabe/tests/app/services/test_ai_lab_leakage.py -q
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from kayfabe.app.services.ai_lab_evaluation import (
    STATUS_DISQUALIFIED,
    STATUS_HELD,
    RetrievalRow,
    summarize_evaluation,
)
from kayfabe.app.services.ai_lab_integrity import PredictionRow, ReportRow
from kayfabe.app.services.ai_lab_knowledge import DocumentRow
from kayfabe.app.services.ai_lab_leakage import DOCUMENT_RULES, summarize_leakage

_SLUG = "summerslam"
_LABEL = "SummerSlam"

_EVENT_START = date(2026, 8, 10)
_GENERATED = datetime(2026, 8, 3, 7, tzinfo=UTC)
_RESULT_AT = datetime(2026, 8, 4, 7, tzinfo=UTC)
#: 경기(8/10)보다 앞서고 예측(8/3)보다도 앞선 개정본 — 어느 규칙에도 안 걸린다.
_CLEAN = datetime(2026, 8, 1, 7, tzinfo=UTC)
#: 예측보다는 나중이고 경기보다는 앞선 개정본. 두 축을 갈라 보는 데 쓴다.
_AFTER_PREDICTION = datetime(2026, 8, 5, 7, tzinfo=UTC)
#: 경기 당일 이후 개정본.
_AFTER_EVENT = datetime(2026, 8, 12, 7, tzinfo=UTC)

_DOC = "https://en.wikipedia.org/wiki/Backlash_(2026)"
_OTHER = "https://en.wikipedia.org/wiki/Cody_Rhodes"
_OWN = "https://en.wikipedia.org/wiki/SummerSlam_(2026)"
_OWN_2 = "https://en.wikipedia.org/wiki/SummerSlam"


def _prediction(
    *,
    match_key: str = "m1",
    generated_at: datetime = _GENERATED,
    finished_at: datetime | None = _RESULT_AT,
    source: str = "agents",
    winner_pick: str | None = "left",
    match_exists: bool = True,
) -> PredictionRow:
    return PredictionRow(
        event_slug=_SLUG,
        event_label=_LABEL,
        match_key=match_key,
        match_title="Title Match",
        pick="left",
        pick_name="Someone",
        win_probability=0.8,
        confidence=0.667,
        rationale="…",
        source=source,
        generated_at=generated_at,
        winner_pick=winner_pick,
        winner_name="Someone",
        finished_at=finished_at,
        event_start_date=_EVENT_START,
        match_exists=match_exists,
    )


def _report(*, match_key: str = "m1", sources: tuple[str, ...] = (_DOC,)) -> ReportRow:
    return ReportRow(
        event_slug=_SLUG,
        match_key=match_key,
        agent="rumor",
        pick="left",
        weight=1.0,
        summary="…",
        sources=sources,
    )


def _document(
    *, url: str = _DOC, revisions: int = 3, revised_at: datetime | None = _CLEAN
) -> DocumentRow:
    return DocumentRow(
        source_url=url,
        source_domain="en.wikipedia.org",
        title=None,
        chunks=3,
        chunks_embedded=3,
        chunks_with_published_at=0,
        first_published_at=None,
        last_collected_at=_AFTER_EVENT,
        chunks_with_revision=revisions,
        latest_revised_at=revised_at,
    )


def _retrieval(
    *,
    match_key: str = "m1",
    url: str = _DOC,
    rank: int = 1,
    revised_at: datetime | None = _CLEAN,
) -> RetrievalRow:
    return RetrievalRow(
        event_slug=_SLUG,
        match_key=match_key,
        source_url=url,
        source_revised_at=revised_at,
        rank=rank,
        source_revision_id=f"1367{rank}",
        published_at=None,
        distance=0.1,
    )


# ---------------------------------------------------------------------------
# 1. 판정을 다시 하지 않는다
# ---------------------------------------------------------------------------


def test_the_graph_repeats_the_verdict_it_was_given() -> None:
    """**그래프가 판정을 새로 내면 두 화면이 다른 말을 하게 된다.**"""
    predictions = [_prediction()]
    reports = [_report(sources=(_OWN,))]
    documents = [_document(url=_OWN)]

    _, _, items, _ = summarize_evaluation(predictions, reports, documents)
    _, graph = summarize_leakage(predictions, reports, documents)

    [edge] = graph[0].predictions
    assert edge.status == items[0].status == STATUS_DISQUALIFIED


def test_only_document_rules_can_appear() -> None:
    """**문서로 돌릴 수 없는 규칙을 코드로 내보내지 않는다.**"""
    _, graph = summarize_leakage(
        [_prediction()], [_report(sources=(_OWN,))], [_document(url=_OWN)]
    )

    assert set(graph[0].codes) <= set(DOCUMENT_RULES)


# ---------------------------------------------------------------------------
# 2. 원인이 여럿이어도 아무도 빠지지 않는다
# ---------------------------------------------------------------------------


def test_two_event_documents_are_both_named() -> None:
    """**반사실만 썼다면 둘 다 무죄가 됐을 자리다.**

    어느 쪽을 빼도 다른 쪽이 자기참조를 남기므로, "빼면 통과하는가"로만 원인을
    가리면 두 문서 모두 원인이 아니라고 말하게 된다. 기여는 규칙이 쓰는 것과 같은
    프리미티브로 직접 읽어야 한다.
    """
    _, graph = summarize_leakage(
        [_prediction()],
        [_report(sources=(_OWN, _OWN_2))],
        [_document(url=_OWN), _document(url=_OWN_2)],
    )

    named = {doc.source_url for doc in graph}
    assert named == {_OWN, _OWN_2}
    assert all(doc.codes == ("self_reference",) for doc in graph)
    # 어느 쪽도 혼자 결정하지 않았다 — 하나를 빼도 판정이 그대로다.
    assert all(doc.sole_cause == 0 for doc in graph)


def test_a_clean_document_in_the_same_prediction_is_not_blamed() -> None:
    """같은 예측에 실려 있다고 원인이 되지는 않는다."""
    _, graph = summarize_leakage(
        [_prediction()],
        [_report(sources=(_OWN, _OTHER))],
        [_document(url=_OWN), _document(url=_OTHER)],
    )

    assert [doc.source_url for doc in graph] == [_OWN]


# ---------------------------------------------------------------------------
# 3. 단독 원인 — 반사실은 여기서만 쓴다
# ---------------------------------------------------------------------------


def test_removing_the_only_offender_would_have_made_it_eligible() -> None:
    """근거가 더 남아 있는데도 그 문서 하나가 판정을 혼자 결정한 경우."""
    totals, graph = summarize_leakage(
        [_prediction()],
        [_report(sources=(_OWN, _OTHER))],
        [_document(url=_OWN), _document(url=_OTHER)],
    )

    [document] = graph
    [edge] = document.predictions
    assert edge.sole_cause is True
    assert edge.sole_evidence is False
    assert document.sole_cause == 1
    assert totals.sole_cause_predictions == 1


def test_the_only_evidence_is_not_counted_as_a_sole_cause() -> None:
    """**근거가 사라져서 통과한 것을 "혼자 막았다"로 세지 않는다.**

    그 문서가 유일한 근거였다면 빼는 순간 인용이 0건이 되고, 코퍼스 규칙은 확인할
    문서가 없다며 통과시킨다. 그 통과를 단독 원인으로 세면 "근거를 지우면 자격을
    얻는다"는 말이 되어, 그래프가 코퍼스를 비우라고 권하는 꼴이 된다.
    """
    totals, graph = summarize_leakage(
        [_prediction()], [_report(sources=(_OWN,))], [_document(url=_OWN)]
    )

    [edge] = graph[0].predictions
    assert edge.sole_evidence is True
    assert edge.sole_cause is False
    assert totals.sole_cause_predictions == 0


# ---------------------------------------------------------------------------
# 4. 합이 맞는다 — 문서로 돌릴 수 없는 것을 감추지 않는다
# ---------------------------------------------------------------------------


def test_a_temporal_inversion_is_not_a_document_problem() -> None:
    """결과 기록 이후에 생성된 것은 **근거의 성질이 아니다.**"""
    totals, graph = summarize_leakage(
        [_prediction(generated_at=_AFTER_EVENT)], [_report()], [_document()]
    )

    assert totals.blocked_predictions == 1
    assert totals.attributed == 0
    assert totals.unattributed == 1
    assert graph == []


def test_the_totals_always_add_up() -> None:
    predictions = [
        _prediction(match_key="m1", generated_at=_AFTER_EVENT),
        _prediction(match_key="m2"),
    ]
    reports = [
        _report(match_key="m1"),
        _report(match_key="m2", sources=(_OWN, _OTHER)),
    ]
    documents = [_document(), _document(url=_OWN), _document(url=_OTHER)]

    totals, _ = summarize_leakage(predictions, reports, documents)

    assert totals.blocked_predictions == totals.attributed + totals.unattributed
    assert totals.blocked_predictions == 2
    assert totals.attributed == 1


def test_excluded_predictions_are_not_blocked() -> None:
    """**제외는 막힌 것이 아니라 묻지 않은 것이다.** 폴백·회수·결과없음이 그렇다."""
    predictions = [
        _prediction(match_key="m1", source="bookmaker_fallback"),
        _prediction(match_key="m2", match_exists=False),
        _prediction(match_key="m3", winner_pick=None, finished_at=None),
    ]
    reports = [_report(match_key=key, sources=(_OWN,)) for key in ("m1", "m2", "m3")]

    totals, graph = summarize_leakage(predictions, reports, [_document(url=_OWN)])

    assert totals.blocked_predictions == 0
    assert graph == []


# ---------------------------------------------------------------------------
# 5. 규칙이 보는 자리를 그대로 따른다
# ---------------------------------------------------------------------------


def test_a_source_only_document_carries_no_time_blame_when_records_exist() -> None:
    """**판정이 보지 않은 문서에 책임을 묻지 않는다.**

    검색 기록이 있으면 코퍼스 규칙은 기록만 본다(`_corpus_from_retrievals`가
    `_corpus`를 이긴다). 그러니 출처에만 있는 문서는 계보가 비어 있어도 시간
    규칙으로 걸리지 않는다 — 자기참조만 남는다.
    """
    _, graph = summarize_leakage(
        [_prediction()],
        [_report(sources=(_OWN,))],
        # 계보가 통째로 비어 있다 — 문서 단위 판정이었다면 보류를 냈을 상태다.
        [_document(url=_OWN, revisions=0, revised_at=None), _document()],
        [_retrieval()],
    )

    [entry] = [doc for doc in graph if doc.source_url == _OWN]
    assert entry.codes == ("self_reference",)


def test_the_revision_rule_only_speaks_where_there_is_a_record() -> None:
    """예측보다 나중에 고쳐진 글은 **기록이 있을 때만** 물을 수 있다.

    그 개정본(8/5)은 경기(8/10)보다는 앞서므로 코퍼스 규칙에는 걸리지 않는다 —
    두 축이 서로 다른 것을 잰다는 사실이 코드 목록에 그대로 드러나야 한다.
    """
    totals, graph = summarize_leakage(
        [_prediction()],
        [_report()],
        [_document()],
        [_retrieval(revised_at=_AFTER_PREDICTION)],
    )

    [document] = graph
    assert document.codes == ("revision_after_prediction",)
    assert document.predictions[0].status == STATUS_HELD
    assert totals.attributed == 1


def test_an_incomplete_lineage_is_read_as_unknown_like_the_rule_does() -> None:
    """계보가 불완전하면 **모르는 것**이다 — 판정이 그렇게 읽으므로 그래프도 그렇다."""
    _, graph = summarize_leakage(
        [_prediction()],
        [_report()],
        # 시각은 있지만 청크 하나가 빈다. `_corpus`는 이것을 통과시키지 않는다.
        [_document(revisions=2)],
    )

    [document] = graph
    assert document.codes == ("unverifiable_corpus",)


def test_a_document_revised_after_the_event_is_named() -> None:
    _, graph = summarize_leakage(
        [_prediction()], [_report()], [_document(revised_at=_AFTER_EVENT)]
    )

    [document] = graph
    assert document.codes == ("unverifiable_corpus",)
    assert document.predictions[0].status == STATUS_HELD


# ---------------------------------------------------------------------------
# 6. 순서와 빈 상태
# ---------------------------------------------------------------------------


def test_the_document_that_blocked_the_most_comes_first() -> None:
    predictions = [_prediction(match_key=f"m{i}") for i in range(1, 4)]
    reports = [
        _report(match_key="m1", sources=(_OWN,)),
        _report(match_key="m2", sources=(_OWN,)),
        _report(match_key="m3", sources=(_OWN_2,)),
    ]
    documents = [_document(url=_OWN), _document(url=_OWN_2)]

    _, graph = summarize_leakage(predictions, reports, documents)

    assert [doc.source_url for doc in graph] == [_OWN, _OWN_2]
    assert [doc.blocked for doc in graph] == [2, 1]


def test_nothing_blocked_means_an_empty_graph_not_an_error() -> None:
    totals, graph = summarize_leakage(
        [_prediction()], [_report()], [_document()], [_retrieval()]
    )

    assert totals.blocked_predictions == 0
    assert totals.documents == 0
    assert graph == []
