"""코퍼스 시간 게이트 계약 테스트 (Phase 3-12).

3-6의 코퍼스 규칙은 인용 문서에 `published_at`이 **있는지**만 봤다. 그 검사는 위키에서
아무것도 증명하지 못한다 — 위키는 그 값을 내보내지 않아 늘 비어 있었고, 채운다 해도
같은 URL이 경기 전후로 계속 고쳐지므로 "그때 결과가 적혀 있었는가"에 답하지 않는다.

여기서 못 박는 계약은 하나다.

    인용 문서를 **우리가 읽은 개정본**이 대회 시작일보다 앞설 때만 ex-ante로 인정한다.
    앞서면 결과가 적혀 있을 수 없다(충분조건). 나머지는 전부 보류다.

**가장 중요한 테스트는 `TestRealWorldGate`다.** 운영에서 실제로 발견한 두 사례를
고정한다 — SummerSlam 문서는 경기 3일 뒤 개정본이라 결과가 통째로 실려 있었고,
MITB 문서는 경기 두 달 전 개정본이라 경기 목록조차 없었다. 게이트가 이 둘을 반대로
판정하면 Phase 3-12가 한 일이 없다.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from kayfabe.app.services.ai_lab_evaluation import (
    STATUS_ELIGIBLE,
    STATUS_HELD,
    DocumentProvenance,
    RetrievalRow,
    summarize_evaluation,
)
from kayfabe.app.services.ai_lab_integrity import PredictionRow, ReportRow
from kayfabe.app.services.ai_lab_knowledge import DocumentRow

#: 인용할 문서. 그 대회 자체를 다룬 문서가 아니라 선수 문서다 — `self_reference`가
#: 먼저 걸리면 코퍼스 규칙까지 판정이 내려오지 않아 이 파일이 재는 것이 사라진다.
_DOC = "https://en.wikipedia.org/wiki/Liv_Morgan"

_EVENT_START = date(2026, 8, 1)
#: 예측 생성 시각. 결과 기록(`finished_at`)보다 앞서야 `temporal_inversion`을 지난다.
_GENERATED = datetime(2026, 7, 20, tzinfo=UTC)
_RECORDED = datetime(2026, 8, 4, tzinfo=UTC)


def _prediction(
    *,
    slug: str = "summerslam",
    label: str = "SummerSlam",
    match_key: str = "m1",
    event_start_date: date | None = _EVENT_START,
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
        rationale="근거 문장.",
        source="agents",
        generated_at=_GENERATED,
        winner_pick="left",
        winner_name="Someone",
        finished_at=_RECORDED,
        event_start_date=event_start_date,
    )


def _report(*, sources: tuple[str, ...] = (_DOC,)) -> ReportRow:
    return ReportRow(
        event_slug="summerslam",
        match_key="m1",
        agent="rumor",
        pick="left",
        weight=0.6,
        summary="요약.",
        sources=sources,
    )


def _document(
    *,
    url: str = _DOC,
    chunks: int = 5,
    chunks_with_revision: int | None = None,
    revised_at: datetime | None = datetime(2026, 7, 10, tzinfo=UTC),
    collected_at: datetime | None = datetime(2026, 7, 15, tzinfo=UTC),
    published: int = 0,
) -> DocumentRow:
    return DocumentRow(
        source_url=url,
        source_domain="en.wikipedia.org",
        title="Liv Morgan",
        chunks=chunks,
        chunks_embedded=chunks,
        chunks_with_published_at=published,
        first_published_at=None,
        last_collected_at=collected_at,
        chunks_with_revision=chunks
        if chunks_with_revision is None
        else chunks_with_revision,
        latest_revised_at=revised_at,
    )


def _status(predictions, reports, documents, retrievals=()) -> str:
    _totals, _rules, items, _perf = summarize_evaluation(
        predictions, reports, documents, retrievals
    )
    return items[0].status


def _retrieval(
    *,
    revised_at: datetime | None,
    url: str = _DOC,
    slug: str = "summerslam",
    match_key: str = "m1",
) -> RetrievalRow:
    return RetrievalRow(
        event_slug=slug,
        match_key=match_key,
        source_url=url,
        source_revised_at=revised_at,
    )


class TestRevisionBeforeEventPasses:
    """CASE B — 경기보다 앞선 개정본이면 통과한다."""

    def test_revision_before_start_date_is_eligible(self) -> None:
        status = _status([_prediction()], [_report()], [_document()])
        assert status == STATUS_ELIGIBLE

    def test_detail_says_what_was_checked(self) -> None:
        _t, _r, items, _p = summarize_evaluation(
            [_prediction()], [_report()], [_document()]
        )
        verdict = next(v for v in items[0].verdicts if v.code == "unverifiable_corpus")
        assert verdict.failed is False
        assert "개정본" in verdict.detail


class TestPublishedAtIsNotEnough:
    """CASE A — **`published_at`이 있어도 통과가 아니다.**

    Phase 3-11이 경고한 바로 그 함정이다. 옛 규칙은 발행일 존재만 보고 통과시켰는데,
    그 값이 있어도 개정본이 경기 뒤면 결과를 봤을 수 있다.
    """

    def test_published_at_present_but_revision_after_event_is_held(self) -> None:
        document = _document(
            published=5,  # 발행일이 **전부** 채워져 있다
            revised_at=datetime(2026, 8, 5, tzinfo=UTC),  # 그러나 개정본은 경기 뒤
        )
        assert _status([_prediction()], [_report()], [document]) == STATUS_HELD


class TestSameDayBoundary:
    """CASE C — 경기 당일 개정본은 통과시키지 않는다.

    당일 개정본에 결과가 없다는 보장이 없다. 비교는 **날짜끼리** 하고 `<`를 쓴다.
    """

    def test_revision_on_start_date_is_held(self) -> None:
        document = _document(revised_at=datetime(2026, 8, 1, 0, 0, tzinfo=UTC))
        assert _status([_prediction()], [_report()], [document]) == STATUS_HELD

    def test_revision_one_day_before_passes(self) -> None:
        # 수집은 개정본 뒤여야 한다 — 앞뒤가 뒤집히면 `is_complete`가 먼저 막는다.
        document = _document(
            revised_at=datetime(2026, 7, 31, 23, 59, tzinfo=UTC),
            collected_at=datetime(2026, 7, 31, 23, 59, tzinfo=UTC),
        )
        assert _status([_prediction()], [_report()], [document]) == STATUS_ELIGIBLE


class TestMissingProvenanceIsHeld:
    """CASE D·E — 모르는 것은 통과가 아니다."""

    def test_missing_revision_is_held(self) -> None:
        # 레거시 668청크가 지나는 길이다.
        document = _document(chunks_with_revision=0, revised_at=None)
        assert _status([_prediction()], [_report()], [document]) == STATUS_HELD

    def test_partial_revision_is_held(self) -> None:
        """청크 5개 중 3개만 계보가 있다 — 하필 그 2개가 검색됐을 수 있다."""
        document = _document(chunks=5, chunks_with_revision=3)
        assert _status([_prediction()], [_report()], [document]) == STATUS_HELD

    def test_missing_event_start_date_is_held(self) -> None:
        # 일정 미정 대회(Bad Blood·King & Queen)가 지나는 길이다.
        prediction = _prediction(event_start_date=None)
        assert _status([prediction], [_report()], [_document()]) == STATUS_HELD

    def test_unknown_document_is_held(self) -> None:
        """인용했는데 코퍼스에 그 문서가 없다 — 판정할 근거가 없다."""
        assert _status([_prediction()], [_report()], []) == STATUS_HELD


class TestCollectedAtOrdering:
    """CASE H — 개정본이 수집보다 나중일 수는 없다."""

    def test_revision_after_collection_is_held(self) -> None:
        document = _document(
            revised_at=datetime(2026, 7, 20, tzinfo=UTC),
            collected_at=datetime(2026, 7, 15, tzinfo=UTC),
        )
        # 개정본 자체는 경기(8/1)보다 앞서지만 수집(7/15)보다 나중이라 앞뒤가 안 맞는다.
        assert _status([_prediction()], [_report()], [document]) == STATUS_HELD

    def test_provenance_is_complete_only_when_ordering_holds(self) -> None:
        ok = DocumentProvenance(
            chunks=3,
            chunks_with_revision=3,
            latest_revised_at=datetime(2026, 7, 10, tzinfo=UTC),
            last_collected_at=datetime(2026, 7, 15, tzinfo=UTC),
        )
        broken = DocumentProvenance(
            chunks=3,
            chunks_with_revision=3,
            latest_revised_at=datetime(2026, 7, 20, tzinfo=UTC),
            last_collected_at=datetime(2026, 7, 15, tzinfo=UTC),
        )
        assert ok.is_complete is True
        assert broken.is_complete is False


class TestNoSourcesStillPasses:
    """출처가 없으면 코퍼스 규칙이 막을 근거가 없다 — 기존 의미를 보존한다."""

    def test_report_without_sources_is_eligible(self) -> None:
        status = _status([_prediction()], [_report(sources=())], [_document()])
        assert status == STATUS_ELIGIBLE


class TestRealWorldGate:
    """CASE I — **운영에서 실제로 발견한 두 사례를 고정한다.**

    이 둘이 반대로 판정되면 Phase 3-12가 한 일이 없다.
    """

    def test_summerslam_revision_after_event_fails(self) -> None:
        """수집한 개정본이 경기 3일 뒤라 결과가 통째로 실려 있었다.

        실측: 리비전 1367773770 = `2026-08-05T03:07:53Z`, 경기 `2026-08-01`.
        본문에 `defeated`가 35회, `pinfall`이 26회 나온다.
        """
        document = _document(
            revised_at=datetime(2026, 8, 5, 3, 7, 53, tzinfo=UTC),
            collected_at=datetime(2026, 8, 5, 3, 38, 23, tzinfo=UTC),
        )
        prediction = _prediction(event_start_date=date(2026, 8, 1))
        assert _status([prediction], [_report()], [document]) == STATUS_HELD

    def test_money_in_the_bank_revision_before_event_passes(self) -> None:
        """수집한 개정본이 경기 두 달 전이라 경기 목록조차 없었다.

        실측: 리비전 1367179316 = `2026-08-01T14:24:04Z`, 경기 `2026-10-10`.
        """
        document = _document(
            revised_at=datetime(2026, 8, 1, 14, 24, 4, tzinfo=UTC),
            collected_at=datetime(2026, 8, 5, 3, 38, 23, tzinfo=UTC),
        )
        prediction = _prediction(
            slug="money-in-the-bank",
            label="Money in the Bank",
            event_start_date=date(2026, 10, 10),
        )
        report = ReportRow(
            event_slug="money-in-the-bank",
            match_key="m1",
            agent="rumor",
            pick="left",
            weight=0.6,
            summary="요약.",
            sources=(_DOC,),
        )
        assert _status([prediction], [report], [document]) == STATUS_ELIGIBLE


class TestRetrievalBeatsTheDocument:
    """**그때 읽은 것으로 판정한다** (Phase 3-13 Stage 4-B).

    문서 단위 판정은 두 군데서 느슨하다. 어느 청크가 뽑혔는지 몰라 그 문서의 가장
    늦은 개정본을 잡고, 그 값이 코퍼스의 *지금* 상태라 재수집이 과거 판정을 바꾼다.
    검색 기록이 있으면 둘 다 없어진다.
    """

    def test_reingest_does_not_change_a_past_verdict(self) -> None:
        """**이 테스트가 Stage 4-B의 존재 이유다.**

        예측은 7/20에 7/10 개정본을 읽고 만들어졌다. 그 뒤 9/19 재수집으로 문서의
        최신 개정본이 경기(8/01) 이후가 됐다 — 운영에서 실제로 일어난 일이다.
        문서만 보면 보류로 뒤집히지만, 읽은 것은 여전히 7/10 개정본이다.
        """
        reingested = _document(
            revised_at=datetime(2026, 9, 19, tzinfo=UTC),
            collected_at=datetime(2026, 9, 19, 12, tzinfo=UTC),
        )
        prediction = _prediction()
        report = _report()

        # 기록이 없으면 재수집이 판정을 뒤집는다 — 이것이 고치려는 상태다.
        assert _status([prediction], [report], [reingested]) == STATUS_HELD

        # 기록이 있으면 그때 읽은 개정본이 판정한다.
        read_back_then = (_retrieval(revised_at=datetime(2026, 7, 10, tzinfo=UTC)),)
        assert (
            _status([prediction], [report], [reingested], read_back_then)
            == STATUS_ELIGIBLE
        )

    def test_a_chunk_read_after_the_match_still_holds(self) -> None:
        """기록을 본다고 느슨해지지 않는다 — 경기 뒤 개정본을 읽었으면 보류다."""
        after = (_retrieval(revised_at=datetime(2026, 8, 5, tzinfo=UTC)),)

        assert (
            _status([_prediction()], [_report()], [_document()], after) == STATUS_HELD
        )

    def test_one_late_chunk_among_many_holds_the_whole(self) -> None:
        """하나라도 늦으면 보류다. 읽은 것 중 무엇이 답에 쓰였는지는 알 수 없다."""
        mixed = (
            _retrieval(revised_at=datetime(2026, 7, 10, tzinfo=UTC)),
            _retrieval(revised_at=datetime(2026, 8, 3, tzinfo=UTC)),
        )

        assert (
            _status([_prediction()], [_report()], [_document()], mixed) == STATUS_HELD
        )

    def test_a_chunk_without_a_revision_holds(self) -> None:
        """레거시 청크를 읽었으면 모르는 것이다 — 모르는 것을 과거로 접지 않는다."""
        unknown = (_retrieval(revised_at=None),)

        assert (
            _status([_prediction()], [_report()], [_document()], unknown) == STATUS_HELD
        )

    def test_records_of_another_match_do_not_leak_in(self) -> None:
        """기록은 경기 키로 묶인다. 남의 기록이 이 예측을 판정하면 안 된다."""
        elsewhere = (
            _retrieval(
                revised_at=datetime(2026, 8, 5, tzinfo=UTC), match_key="other-match"
            ),
        )

        # 이 예측에는 기록이 없으므로 문서 단위로 판정된다(7/10 개정본 → 자격).
        assert (
            _status([_prediction()], [_report()], [_document()], elsewhere)
            == STATUS_ELIGIBLE
        )

    def test_it_judges_even_when_no_source_was_cited(self) -> None:
        """출처를 안 적었어도 읽은 것은 읽은 것이다.

        문서 단위 경로는 "인용 출처 0건이면 통과"인데, 그건 리포트가 URL을 안
        적었다는 뜻이지 아무것도 안 읽었다는 뜻이 아니다.
        """
        late = (_retrieval(revised_at=datetime(2026, 8, 5, tzinfo=UTC)),)

        assert _status([_prediction()], [_report(sources=())], [_document()]) == (
            STATUS_ELIGIBLE
        )
        assert (
            _status([_prediction()], [_report(sources=())], [_document()], late)
            == STATUS_HELD
        )
