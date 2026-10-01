"""`status` 드리프트 판정과 쓰기 범위를 고정한다.

`scripts/close_past_events.py`의 테스트와 **같은 판정**을 본다 — 판정이 도메인
(`domain/services/event_status_drift.py`)으로 올라가 둘이 그것을 공유한다. 여기서
확인하는 것은 유스케이스가 그 판정을 **어디까지 쓰기로 옮기는가**다.
"""

from __future__ import annotations

from datetime import date

import pytest

from kayfabe.app.dtos.event_status_dto import EventScheduleRow
from kayfabe.app.use_cases.event_status_interactor import EventStatusInteractor

_TODAY = date(2026, 10, 1)


class FakeRepository:
    def __init__(
        self, rows: list[EventScheduleRow], *, missing: set[str] | None = None
    ):
        self._rows = rows
        self._missing = missing or set()
        self.writes: list[tuple[str, str]] = []

    async def list_event_schedules(self) -> list[EventScheduleRow]:
        return list(self._rows)

    async def set_event_status(self, *, slug: str, status: str) -> bool:
        if slug in self._missing:
            return False
        self.writes.append((slug, status))
        return True


def _row(slug: str, status: str, start: str | None, end: str | None = None):
    return EventScheduleRow(
        slug=slug,
        status=status,
        start_date=date.fromisoformat(start) if start else None,
        end_date=date.fromisoformat(end) if end else None,
    )


_ROWS = [
    # 날짜가 지났는데 안 닫힌 둘 — upcoming과 live 모두 대상이다.
    _row("clash-in-italy", "upcoming", "2026-05-31"),
    _row("summerslam", "live", "2026-08-01", "2026-08-02"),
    # 오늘 열리는 대회는 넘기지 않는다.
    _row("today-event", "upcoming", "2026-10-01"),
    # 아직 안 지났다.
    _row("money-in-the-bank", "upcoming", "2026-10-10"),
    # 이미 닫혔다 — 되돌리지 않는다.
    _row("royal-rumble", "finished", "2026-01-31"),
    # 날짜 미상 — 통과가 아니라 보류다.
    _row("bad-blood", "upcoming", None),
]


@pytest.mark.asyncio
async def test_preview_writes_nothing() -> None:
    repository = FakeRepository(_ROWS)

    report = await EventStatusInteractor(repository).preview(today=_TODAY)

    assert repository.writes == []
    assert report.pending == 2
    # `None`이 "쓰지 않았다"다 — 0("쓸 게 없었다")과 구분된다.
    assert report.written is None


@pytest.mark.asyncio
async def test_preview_labels_every_row() -> None:
    report = await EventStatusInteractor(FakeRepository(_ROWS)).preview(today=_TODAY)

    verdicts = {item.slug: item.verdict for item in report.items}
    assert verdicts == {
        "clash-in-italy": "needs_close",
        "summerslam": "needs_close",
        "today-event": "upcoming",
        "money-in-the-bank": "upcoming",
        "royal-rumble": "already_finished",
        "bad-blood": "unknown_date",
    }
    # slug 순서로 정렬해 내려준다 — 화면이 매번 같은 줄 순서를 본다.
    assert [item.slug for item in report.items] == sorted(verdicts)


@pytest.mark.asyncio
async def test_close_past_writes_only_drifted_rows() -> None:
    repository = FakeRepository(_ROWS)

    report = await EventStatusInteractor(repository).close_past(today=_TODAY)

    assert repository.writes == [
        ("clash-in-italy", "finished"),
        ("summerslam", "finished"),
    ]
    assert report.written == 2


@pytest.mark.asyncio
async def test_close_past_reports_what_it_changed_not_the_new_state() -> None:
    """쓰기 전 판정을 돌려준다 — 다시 읽으면 무엇을 바꿨는지가 사라진다."""
    report = await EventStatusInteractor(FakeRepository(_ROWS)).close_past(today=_TODAY)

    closed = [item.slug for item in report.items if item.verdict == "needs_close"]
    assert closed == ["clash-in-italy", "summerslam"]


@pytest.mark.asyncio
async def test_close_past_is_idempotent() -> None:
    """이미 다 닫힌 목록에서는 아무것도 쓰지 않는다."""
    rows = [_row("royal-rumble", "finished", "2026-01-31")]
    repository = FakeRepository(rows)

    report = await EventStatusInteractor(repository).close_past(today=_TODAY)

    assert repository.writes == []
    assert (report.pending, report.written) == (0, 0)


@pytest.mark.asyncio
async def test_vanished_row_is_not_swallowed() -> None:
    """읽은 뒤 쓰기 사이에 행이 사라지면 조용히 넘기지 않는다."""
    repository = FakeRepository(_ROWS, missing={"clash-in-italy"})

    with pytest.raises(LookupError):
        await EventStatusInteractor(repository).close_past(today=_TODAY)
