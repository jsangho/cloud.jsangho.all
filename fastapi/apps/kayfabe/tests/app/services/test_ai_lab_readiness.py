"""코퍼스 준비도 (Phase 8).

**이 화면이 지키는 것은 시제(時制)의 정직함이다.** 나머지 AI LAB 화면은 이미 만들어진
예측을 놓고 무엇이 막혔는지 말하는데, 이것만 아직 없는 예측을 놓고 무엇이 막을지
말한다. 그래서 틀리기 쉬운 자리가 넷이다.

1. **판정과 위험을 섞으면 안 된다** — 여기 나오는 것은 어떤 예측의 상태도 아니다.
   자격은 예측이 생긴 뒤에 `summarize_evaluation`이 정한다.
2. **규칙이 쓰는 함수를 그대로 써야 한다** — 비교를 따로 적으면 이 화면이
   "괜찮다"고 한 대회를 판정이 막는다.
3. **날짜가 사실이고 `status`는 사람의 기록이다** — 지난 대회를 닫는 일은 사람이
   스크립트로 하므로 그 칸은 드리프트한다.
4. **못 보는 것을 세어야 한다** — 날짜 없는 대회를 조용히 빼면 목록이 전부인 척한다.

실행:

    cd fastapi
    PYTHONUTF8=1 PYTHONPATH=apps uv run pytest \\
        apps/kayfabe/tests/app/services/test_ai_lab_readiness.py -q
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from kayfabe.app.services.ai_lab_integrity import PredictionRow
from kayfabe.app.services.ai_lab_knowledge import DocumentRow
from kayfabe.app.services.ai_lab_readiness import (
    FORESEEABLE_RULES,
    RISK_CLEAR,
    RISK_DISQUALIFY,
    RISK_HOLD,
    EventRow,
    summarize_readiness,
)

_TODAY = date(2026, 9, 23)
#: 오늘 이후의 대회. 지뢰가 없으면 이 대회는 깨끗하다.
_SOON = date(2026, 10, 10)

_CLEAN_REVISION = datetime(2026, 9, 1, 7, tzinfo=UTC)
_COLLECTED = datetime(2026, 9, 20, 7, tzinfo=UTC)

_OTHER = "https://en.wikipedia.org/wiki/Cody_Rhodes"
_OWN = "https://en.wikipedia.org/wiki/Money_in_the_Bank_(2026)"


def _event(
    *,
    slug: str = "money-in-the-bank",
    label: str = "Money in the Bank",
    start_date: date | None = _SOON,
    status: str = "upcoming",
    matches: int = 3,
) -> EventRow:
    return EventRow(
        slug=slug,
        label=label,
        start_date=start_date,
        status=status,
        matches=matches,
    )


def _document(
    *,
    url: str = _OTHER,
    chunks: int = 3,
    revisions: int = 3,
    revised_at: datetime | None = _CLEAN_REVISION,
    embedded: int = 3,
) -> DocumentRow:
    return DocumentRow(
        source_url=url,
        source_domain="en.wikipedia.org",
        title=None,
        chunks=chunks,
        chunks_embedded=embedded,
        chunks_with_published_at=0,
        first_published_at=None,
        last_collected_at=_COLLECTED,
        chunks_with_revision=revisions,
        latest_revised_at=revised_at,
    )


def _prediction(
    *, slug: str = "money-in-the-bank", match_key: str = "m1"
) -> PredictionRow:
    return PredictionRow(
        event_slug=slug,
        event_label="Money in the Bank",
        match_key=match_key,
        match_title="Ladder Match",
        pick="left",
        pick_name="Someone",
        win_probability=0.8,
        confidence=0.6,
        rationale="…",
        source="agents",
        generated_at=datetime(2026, 9, 21, 7, tzinfo=UTC),
        winner_pick=None,
        winner_name=None,
        event_start_date=_SOON,
    )


def _summarize(events=None, documents=None, predictions=None, *, as_of=_TODAY):
    return summarize_readiness(
        events if events is not None else [_event()],
        documents if documents is not None else [_document()],
        predictions if predictions is not None else [],
        as_of=as_of,
    )


# ---------------------------------------------------------------------------
# 1. 지뢰 — 그 대회 자체를 다룬 문서
# ---------------------------------------------------------------------------


class TestSelfReferenceMines:
    def test_a_document_about_the_event_is_a_mine(self) -> None:
        _, _, items = _summarize(documents=[_document(url=_OWN)])
        assert [mine.source_url for mine in items[0].mines] == [_OWN]
        assert items[0].risk == RISK_DISQUALIFY

    def test_an_unrelated_document_is_not_a_mine(self) -> None:
        _, _, items = _summarize()
        assert items[0].mines == ()
        assert items[0].risk == RISK_CLEAR

    def test_a_longer_event_name_does_not_catch_a_shorter_one(self) -> None:
        """`cites_own_event`와 **같은 판정**이다 — 포함이 아니라 시작으로 본다.

        "Night of Champions" 문서가 "Champions" 대회의 지뢰가 되면, 화면이 없는
        누수를 만들어 멀쩡한 문서를 빼라고 권하게 된다.
        """
        _, _, items = _summarize(
            events=[_event(slug="champions", label="Champions")],
            documents=[
                _document(url="https://en.wikipedia.org/wiki/Night_of_Champions_(2026)")
            ],
        )
        assert items[0].mines == ()

    def test_an_unembedded_document_is_still_a_mine(self) -> None:
        """임베딩이 없어 지금은 안 뽑히지만, 임베딩은 나중에 채워진다.

        묻는 것은 "지금 뽑히는가"가 아니라 "코퍼스에 있는가"다 — 조치도 그쪽이다.
        """
        _, corpus, items = _summarize(documents=[_document(url=_OWN, embedded=0)])
        assert [mine.source_url for mine in items[0].mines] == [_OWN]
        assert corpus.unembedded_documents == 1

    def test_mines_are_ordered_by_size_then_url(self) -> None:
        big = _document(url=_OWN, chunks=9, revisions=9)
        small = _document(url="https://en.wikipedia.org/wiki/Money_in_the_Bank")
        _, _, items = _summarize(documents=[small, big])
        assert [mine.chunks for mine in items[0].mines] == [9, 3]


# ---------------------------------------------------------------------------
# 2. 위험도 — 무게가 다른 둘을 접지 않는다
# ---------------------------------------------------------------------------


class TestRisk:
    def test_incomplete_lineage_alone_is_a_hold_risk(self) -> None:
        """계보가 불완전하면 보류이지 실격이 아니다 — 규칙의 무게 그대로다."""
        _, _, items = _summarize(documents=[_document(revisions=1)])
        assert items[0].unverifiable_documents == 1
        assert items[0].risk == RISK_HOLD

    def test_self_reference_outranks_an_incomplete_lineage(self) -> None:
        """둘 다일 때 가벼운 쪽을 말하면 화면이 위험을 낮춰 보고한다."""
        _, _, items = _summarize(
            documents=[_document(url=_OWN), _document(revisions=1)]
        )
        assert items[0].risk == RISK_DISQUALIFY

    def test_a_clean_corpus_is_clear(self) -> None:
        totals, _, items = _summarize()
        assert items[0].risk == RISK_CLEAR
        assert totals.clear == 1

    def test_the_three_risks_add_up_to_the_event_count(self) -> None:
        """합이 안 맞으면 화면이 대회 하나를 감춘 것이다."""
        totals, _, _ = _summarize(
            events=[
                _event(slug="a", label="Alpha"),
                _event(slug="b", label="Money in the Bank"),
            ],
            documents=[_document(url=_OWN), _document(revisions=1)],
        )
        assert totals.events == totals.clear + totals.hold_risk + totals.disqualify_risk


# ---------------------------------------------------------------------------
# 3. 시간 — 날짜가 사실이고 status는 기록이다
# ---------------------------------------------------------------------------


class TestTimeWindow:
    def test_a_past_event_is_not_listed(self) -> None:
        _, _, items = _summarize(events=[_event(start_date=date(2026, 9, 1))])
        assert items == []

    def test_today_is_still_ahead(self) -> None:
        """경계는 `>=`다 — 오늘 열리는 대회의 예측은 아직 만들 수 있다."""
        _, _, items = _summarize(events=[_event(start_date=_TODAY)])
        assert [item.days_until for item in items] == [0]

    def test_a_drifted_status_does_not_remove_the_event(self) -> None:
        """`close_past_events.py`를 사람이 돌리므로 `status`는 늦는다.

        날짜가 앞에 있으면 상태가 무엇이든 목록에 남고, 상태는 **싣기만** 한다.
        """
        _, _, items = _summarize(events=[_event(status="finished")])
        assert [item.status for item in items] == ["finished"]

    def test_an_undated_event_is_counted_not_hidden(self) -> None:
        """조용히 빼면 목록이 전부인 척한다."""
        totals, _, items = _summarize(events=[_event(start_date=None)])
        assert items == []
        assert totals.undated_events == 1

    def test_events_are_ordered_by_date(self) -> None:
        _, _, items = _summarize(
            events=[
                _event(slug="later", label="Later", start_date=date(2026, 11, 1)),
                _event(slug="sooner", label="Sooner", start_date=date(2026, 10, 1)),
            ]
        )
        assert [item.slug for item in items] == ["sooner", "later"]


# ---------------------------------------------------------------------------
# 4. 집계 — 분모를 정직하게 센다
# ---------------------------------------------------------------------------


class TestTotals:
    def test_predictions_are_counted_per_match_not_per_row(self) -> None:
        """같은 경기의 예측이 둘이어도 예측된 경기는 하나다."""
        _, _, items = _summarize(
            predictions=[_prediction(), _prediction(), _prediction(match_key="m2")]
        )
        assert items[0].predicted == 2
        assert items[0].matches == 3

    def test_predictions_for_other_events_do_not_count(self) -> None:
        _, _, items = _summarize(predictions=[_prediction(slug="summerslam")])
        assert items[0].predicted == 0

    def test_a_mine_shared_by_two_events_is_counted_once(self) -> None:
        """대회를 가로질러 중복 없이 센다 — 같은 문서를 두 번 빼지는 않는다."""
        totals, _, items = _summarize(
            events=[
                _event(slug="mitb", label="Money in the Bank"),
                _event(slug="mitb-2", label="Money in the Bank", matches=2),
            ],
            documents=[_document(url=_OWN)],
        )
        assert [len(item.mines) for item in items] == [1, 1]
        assert totals.mine_documents == 1

    def test_the_corpus_tile_counts_documents_not_chunks(self) -> None:
        _, corpus, _ = _summarize(
            documents=[_document(), _document(url=_OWN, revisions=1)]
        )
        assert corpus.documents == 2
        assert corpus.incomplete_lineage == 1


# ---------------------------------------------------------------------------
# 5. 경계 — 이 화면이 하지 않는 일
# ---------------------------------------------------------------------------


class TestBoundaries:
    def test_only_two_rules_can_be_foreseen(self) -> None:
        """`revision_after_prediction`은 견줄 예측 시각이 아직 없다.

        목록에 끼워 넣으면 화면이 물을 수 없는 것을 물은 척 세운다.
        """
        assert FORESEEABLE_RULES == ("self_reference", "unverifiable_corpus")

    def test_the_same_incomplete_document_weighs_on_every_event(self) -> None:
        """계보는 **문서의 성질**이라 대회를 가리지 않는다.

        그래서 그 문서들은 대회 목록이 아니라 코퍼스 칸에 한 번 선다 — 대회마다
        같은 목록을 실으면 화면이 대회마다 다른 문제인 척하게 된다.
        """
        _, corpus, items = _summarize(
            events=[
                _event(slug="a", label="Alpha"),
                _event(slug="b", label="Bravo", start_date=date(2026, 11, 1)),
            ],
            documents=[_document(revisions=1)],
        )
        assert [item.unverifiable_documents for item in items] == [1, 1]
        assert corpus.incomplete_lineage == 1

    def test_an_empty_corpus_blocks_nothing(self) -> None:
        """문서가 없으면 인용할 것도 없다 — 없음을 위험으로 세지 않는다."""
        totals, corpus, items = _summarize(documents=[])
        assert items[0].risk == RISK_CLEAR
        assert corpus.documents == 0
        assert totals.mine_documents == 0
