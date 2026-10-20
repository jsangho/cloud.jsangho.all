"""대회 `finished_at` 봉인 판정 (`domain/services/event_seal`).

이 파일이 붙드는 것은 넷이다.

1. 결과가 **전부** 들어왔고 대회 칸이 비었을 때만 봉인한다.
2. **부분 기록은 봉인하지 않는다** — 다 들어온 것과 일부만 들어온 것을 같은 시각으로
   봉인하면 나중에 구분할 수 없다.
3. **값이 있으면 덮지 않는다.**
4. 봉인 시각은 `now()`가 아니라 **`max(경기 finished_at)`** 이다. 백필과 같은 뜻을
   써야 두 경로가 갈리지 않는다.

순수 함수라 DB도 시간도 필요 없다.
"""

from __future__ import annotations

from datetime import UTC, datetime

from kayfabe.domain.services.event_seal import EventSealState, seal_decision

_EARLY = datetime(2026, 10, 7, 8, 29, 27, tzinfo=UTC)
_LATE = datetime(2026, 10, 7, 8, 29, 29, tzinfo=UTC)


def _state(
    *,
    matches: int = 5,
    results: int = 5,
    latest: datetime | None = _LATE,
    current: datetime | None = None,
) -> EventSealState:
    return EventSealState(
        slug="heatwave",
        match_count=matches,
        result_count=results,
        latest_match_finished_at=latest,
        event_finished_at=current,
    )


class TestSeals:
    def test_all_results_in_seals_at_latest_match_time(self) -> None:
        assert seal_decision(_state()) == _LATE

    def test_uses_the_max_not_the_min(self) -> None:
        """경기 시각이 여럿이면 **최대값**이다. 어댑터가 `max()`로 읽어 주고,
        판정은 받은 값을 그대로 쓴다 — 여기서 보는 것은 그 값이 통과한다는 것."""
        assert seal_decision(_state(latest=_EARLY)) == _EARLY


class TestHolds:
    def test_partial_results_do_not_seal(self) -> None:
        assert seal_decision(_state(matches=5, results=4)) is None

    def test_no_results_does_not_seal(self) -> None:
        assert seal_decision(_state(matches=5, results=0)) is None

    def test_existing_value_is_never_overwritten(self) -> None:
        assert seal_decision(_state(current=_EARLY)) is None

    def test_existing_value_wins_even_when_latest_is_newer(self) -> None:
        """덮어쓰기는 **어떤 경우에도** 없다 — 더 새 시각을 알아도 그렇다."""
        assert seal_decision(_state(current=_EARLY, latest=_LATE)) is None

    def test_zero_matches_does_not_seal(self) -> None:
        """경기가 0건이면 "다 들어왔다"가 공허하게 참이 된다. 보류여야 한다."""
        assert seal_decision(_state(matches=0, results=0)) is None

    def test_missing_match_timestamps_hold(self) -> None:
        """경기에 시각이 없으면 재구성할 재료가 없다. 지어내지 않는다."""
        assert seal_decision(_state(latest=None)) is None


class TestAllResultsIn:
    def test_zero_matches_is_not_all_in(self) -> None:
        assert _state(matches=0, results=0).all_results_in is False

    def test_full_is_all_in(self) -> None:
        assert _state(matches=7, results=7).all_results_in is True
