"""읽은 글이 **예측보다 먼저 있던 글인가** (Phase 2).

골든 세트(`test_eligibility_golden_set.py`)는 이 축이 최종 상태에 어떻게 반영되는지를
표로 못 박는다. 여기서는 그 표가 **왜 그렇게 나오는지** — 경계값과 표시대(tz)와
`temporal_inversion`과의 독립성을 — 따로 잰다.

**이 규칙이 잡는 것은 누수가 아니라 불가능한 기록이다.** 개정본이 예측보다 나중이면
그 글은 예측을 만들 때 존재하지 않았고, 따라서 "이것을 읽었다"는 기록이 사실일 수
없다. 결과를 봤다는 뜻은 아니므로 실격이 아니라 보류다.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta, timezone

from kayfabe.app.services.ai_lab_evaluation import (
    REVISION_AFTER_PREDICTION,
    REVISION_BEFORE_PREDICTION,
    REVISION_UNKNOWN,
    RetrievalRow,
    explain_evidence,
    summarize_evaluation,
)
from kayfabe.app.services.ai_lab_integrity import PredictionRow, ReportRow
from kayfabe.app.services.ai_lab_knowledge import DocumentRow

_SLUG = "summerslam"
_LABEL = "SummerSlam"
_MATCH = "m1"
_DOC = "https://en.wikipedia.org/wiki/Cody_Rhodes"

_EVENT_DAY = date(2026, 8, 10)
_GENERATED_AT = datetime(2026, 8, 5, 7, tzinfo=UTC)
_RESULT_RECORDED_AT = datetime(2026, 8, 11, 7, tzinfo=UTC)

#: 예측보다 앞선 개정본 — 그때 실제로 읽을 수 있던 글이다.
_REVISED_BEFORE = datetime(2026, 8, 1, 7, tzinfo=UTC)

#: 예측보다 나중이지만 **대회보다는 앞선** 개정본. 코퍼스 규칙은 지나므로 이 축만 잰다.
_REVISED_AFTER = datetime(2026, 8, 7, 3, tzinfo=UTC)

KST = timezone(timedelta(hours=9))


def _prediction(
    *,
    generated_at: datetime = _GENERATED_AT,
    finished_at: datetime | None = _RESULT_RECORDED_AT,
) -> PredictionRow:
    return PredictionRow(
        event_slug=_SLUG,
        event_label=_LABEL,
        match_key=_MATCH,
        match_title="World Heavyweight Championship",
        pick="left",
        pick_name="Cody Rhodes",
        win_probability=0.7,
        confidence=0.6,
        rationale="…",
        source="agents",
        generated_at=generated_at,
        winner_pick="left",
        winner_name="Cody Rhodes",
        finished_at=finished_at,
        outcome_known_externally=None,
        provenance_note=None,
        event_start_date=_EVENT_DAY,
        match_exists=True,
    )


def _report() -> ReportRow:
    return ReportRow(
        event_slug=_SLUG,
        match_key=_MATCH,
        agent="storyline",
        pick="left",
        weight=1.0,
        summary="…",
        sources=(_DOC,),
    )


def _document() -> DocumentRow:
    """계보가 완전하고 경기보다 앞선 문서. 기록이 없는 경로에서만 쓰인다."""
    return DocumentRow(
        source_url=_DOC,
        source_domain="en.wikipedia.org",
        title=None,
        chunks=3,
        chunks_embedded=3,
        chunks_with_published_at=0,
        first_published_at=None,
        last_collected_at=datetime(2026, 8, 18, 7, tzinfo=UTC),
        chunks_with_revision=3,
        latest_revised_at=_REVISED_BEFORE,
    )


def _retrieval(rank: int, revised_at: datetime | None) -> RetrievalRow:
    return RetrievalRow(
        event_slug=_SLUG,
        match_key=_MATCH,
        source_url=_DOC,
        source_revised_at=revised_at,
        rank=rank,
    )


def _judge(*retrievals: RetrievalRow, prediction: PredictionRow | None = None):
    _, _, items, _ = summarize_evaluation(
        [prediction or _prediction()],
        [_report()],
        [_document()],
        list(retrievals),
    )
    return items[0]


def _verdict(item, code: str):
    return next(v for v in item.verdicts if v.code == code)


# ---------------------------------------------------------------------------
# 1. 세 자리 — 앞섰다 · 나중이다 · 모른다
# ---------------------------------------------------------------------------


def test_a_revision_older_than_the_prediction_passes() -> None:
    """그때 읽을 수 있던 글이면 이 규칙은 아무것도 막지 않는다."""
    item = _judge(_retrieval(1, _REVISED_BEFORE))

    assert item.status == "eligible"
    assert _verdict(item, "revision_after_prediction").failed is False


def test_a_revision_newer_than_the_prediction_holds_it() -> None:
    """**예측이 읽을 수 없었던 글**이 증거에 있으면 보류다.

    실격이 아닌 이유는 이것이 누수의 증거가 아니기 때문이다 — 기록이 성립하지 않을
    뿐이고, 성립하지 않는 증거로는 자격을 줄 수도 실격을 줄 수도 없다.
    """
    item = _judge(_retrieval(1, _REVISED_AFTER))

    assert item.status == "held"
    assert _verdict(item, "revision_after_prediction").failed is True
    # 다른 규칙을 끌어들이지 않았다 — 이 입력은 경기일 기준으로는 깨끗하다.
    assert _verdict(item, "unverifiable_corpus").failed is False
    assert _verdict(item, "temporal_inversion").failed is False


def test_an_unknown_revision_is_left_to_the_corpus_rule() -> None:
    """모름은 `unverifiable_corpus`가 잡는다. **여기서 두 번 세지 않는다.**

    두 규칙이 같은 결손을 각각 세면 "왜 막혔나"가 두 배로 부풀고, 새 규칙이 실제로
    잡는 것(불가능한 기록)이 무엇인지 흐려진다. 대신 사유 문장이 **아는 것만
    봤다**고 적어, 전량을 확인한 척하지 않는다.
    """
    item = _judge(_retrieval(1, None))

    assert item.status == "held"
    assert _verdict(item, "unverifiable_corpus").failed is True
    mine = _verdict(item, "revision_after_prediction")
    assert mine.failed is False
    assert "시각이 없어" in mine.detail


def test_the_detail_counts_only_what_it_could_check() -> None:
    """섞여 있으면 **아는 것의 수**를 적는다. 전량을 확인했다고 말하지 않는다."""
    item = _judge(_retrieval(1, _REVISED_BEFORE), _retrieval(2, None))

    detail = _verdict(item, "revision_after_prediction").detail
    assert "시각을 아는 1건" in detail


# ---------------------------------------------------------------------------
# 2. 경계값과 표시대
# ---------------------------------------------------------------------------


def test_the_same_instant_is_not_after() -> None:
    """**경계값.** `>`를 `>=`로 바꾸면 여기가 막힌다.

    경기일 비교(`_temporal_position`)가 `>=`인 것과 달라 보이지만 원칙은 같다.
    그쪽은 `DATE`라 '같은 날'이 하루 전체를 가리키고 그 안에 경기가 들어 있지만,
    여기 둘은 초 단위 시각이라 '같은 순간'은 말 그대로 한 점이다.
    """
    item = _judge(_retrieval(1, _GENERATED_AT))

    assert _verdict(item, "revision_after_prediction").failed is False
    assert item.status == "eligible"


def test_one_second_later_is_after() -> None:
    """경계의 반대편. 1초 뒤는 미래다 — `>`가 실제로 갈리는 자리를 고정한다."""
    item = _judge(_retrieval(1, _GENERATED_AT + timedelta(seconds=1)))

    assert _verdict(item, "revision_after_prediction").failed is True


def test_the_same_instant_written_in_another_timezone_is_not_after() -> None:
    """**표시대가 달라도 같은 순간은 같은 순간이다.**

    KST 16:00 = UTC 07:00. 문자열이나 시계 숫자로 비교하면 9시간 뒤로 보여 멀쩡한
    기록이 불가능한 기록으로 둔갑한다.
    """
    item = _judge(_retrieval(1, datetime(2026, 8, 5, 16, tzinfo=KST)))

    assert _verdict(item, "revision_after_prediction").failed is False


def test_a_naive_timestamp_is_read_as_utc_instead_of_crashing() -> None:
    """표시가 빠진 값(SQLite가 그렇다)을 UTC로 읽는다. **시각을 옮기지 않는다.**

    그냥 비교하면 `TypeError`로 터지는데, 그것은 "판정할 수 없다"가 아니라 사고다.
    판정 엔진이 저장소 종류에 따라 죽는 일이 없어야 한다.
    """
    naive_before = datetime(2026, 8, 1, 7)
    naive_after = datetime(2026, 8, 7, 3)

    older = _verdict(_judge(_retrieval(1, naive_before)), "revision_after_prediction")
    newer = _verdict(_judge(_retrieval(1, naive_after)), "revision_after_prediction")

    assert (older.failed, newer.failed) == (False, True)


# ---------------------------------------------------------------------------
# 3. 다른 규칙과 섞이지 않는다
# ---------------------------------------------------------------------------


def test_it_is_independent_of_temporal_inversion() -> None:
    """**두 시간 규칙은 서로 다른 것을 잰다.**

    `temporal_inversion`은 *결과*와 예측의 선후이고, 이 규칙은 *근거*와 예측의
    선후다. 결과 기록보다 먼저 만든 예측이어도 증거가 미래에서 왔을 수 있다 —
    한 규칙으로 접으면 화면이 원인을 틀리게 말한다.
    """
    item = _judge(_retrieval(1, _REVISED_AFTER))

    assert _verdict(item, "temporal_inversion").failed is False
    assert _verdict(item, "revision_after_prediction").failed is True


def test_a_prediction_without_a_snapshot_is_not_judged_by_this_rule() -> None:
    """**기록이 없으면 묻지 않는다** — 옛 예측 판정이 한 칸도 움직이지 않는다.

    물음의 주어가 "읽었다고 기록된 글"이라, 기록이 없으면 참도 거짓도 아니다.
    `applicable=False`로 적으면 "재려 했는데 못 쟀다"는 다른 말이 되고, Stage 4
    이전에 만든 예측 전부가 소급해서 보류로 떨어진다.
    """
    item = _judge()

    assert [v.code for v in item.verdicts] == [
        "temporal_inversion",
        "self_reference",
        "unverifiable_corpus",
    ]
    assert item.status == "eligible"


def test_the_rule_tally_does_not_count_predictions_without_snapshots() -> None:
    """규칙 표가 **기록이 없다는 이유로** 건수를 부풀리지 않는다."""
    _, rules, _, _ = summarize_evaluation(
        [_prediction(generated_at=datetime(2026, 8, 12, 7, tzinfo=UTC))],
        [_report()],
        [_document()],
        [],
    )
    by_code = {rule.code: rule.blocked for rule in rules}

    # 이 예측은 결과 기록 뒤에 만들어져 실격이다 — 그러나 새 규칙과는 무관하다.
    assert by_code["temporal_inversion"] == 1
    assert by_code["revision_after_prediction"] == 0


# ---------------------------------------------------------------------------
# 4. 화면이 판정과 같은 값을 받는다
# ---------------------------------------------------------------------------


def test_the_audit_screen_gets_the_same_three_positions() -> None:
    """감사 화면은 판정과 **같은 함수**를 지난다 (Phase 9와 같은 규율).

    화면이 따로 계산하면 언젠가 한쪽만 바뀌어, 규칙은 보류라는데 증거 줄은 전부
    초록으로 보이는 일이 생긴다.
    """
    verdicts = explain_evidence(
        (
            _retrieval(1, _REVISED_BEFORE),
            _retrieval(2, _REVISED_AFTER),
            _retrieval(3, None),
        ),
        event_label=_LABEL,
        event_start_date=_EVENT_DAY,
        generated_at=_GENERATED_AT,
    )

    assert [v.revision_vs_prediction for v in verdicts] == [
        REVISION_BEFORE_PREDICTION,
        REVISION_AFTER_PREDICTION,
        REVISION_UNKNOWN,
    ]


def test_the_two_temporal_axes_are_reported_separately() -> None:
    """같은 청크가 **경기 기준으로는 깨끗하고 예측 기준으로는 불가능**할 수 있다.

    한 칸으로 합치면 이 조합을 표현할 방법이 없어진다.
    """
    [verdict] = explain_evidence(
        (_retrieval(1, _REVISED_AFTER),),
        event_label=_LABEL,
        event_start_date=_EVENT_DAY,
        generated_at=_GENERATED_AT,
    )

    assert verdict.temporal == "before_event"
    assert verdict.revision_vs_prediction == REVISION_AFTER_PREDICTION
