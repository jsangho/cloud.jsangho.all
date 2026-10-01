"""대회 `status` 드리프트 점검 — `close_past_events.py`와 **같은 판정**을 쓴다.

스크립트가 하지 않는 것을 이쪽도 하지 않는다:

- **`finished_at`을 쓰지 않는다.** 기존 `finished` 대회의 `finished_at`은 전부 카드
  동기화가 돌던 시각, 즉 "결과가 기록된 시각"이다. 날짜가 지났다는 사실은 결과가
  기록됐다는 뜻이 아니므로 그것을 지어낼 수 없다.
- **경기를 건드리지 않는다.** 결과가 없는 대회에서 경기를 `finished`로 넘길 근거가 없다.
- **`finished`를 되돌리지 않는다.** 한 방향으로만 흐른다.
- **값이 같으면 쓰지 않는다** — 멱등이다. `updated_at`이 `onupdate`로 함께 실리므로
  무변경 쓰기는 "이 행이 언제 바뀌었나"를 거짓으로 만든다.

커밋하지 않는다 — 트랜잭션 경계는 `get_db`가 요청 끝에서 정한다.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime

from kayfabe.app.dtos.event_status_dto import (
    EventStatusDriftItem,
    EventStatusDriftReport,
)
from kayfabe.app.ports.input.event_status_use_case import EventStatusUseCase
from kayfabe.app.ports.output.event_status_repository import EventStatusRepository
from kayfabe.domain.services.event_status_drift import StatusChange
from kayfabe.domain.value_objects.ple_status_vo import PleEventStatus

logger = logging.getLogger("uvicorn.error")


class EventStatusInteractor(EventStatusUseCase):
    def __init__(self, repository: EventStatusRepository) -> None:
        self._repository = repository

    async def preview(self, *, today: date | None = None) -> EventStatusDriftReport:
        day = today or datetime.now(UTC).date()
        return _report(day, await self._collect(day))

    async def close_past(self, *, today: date | None = None) -> EventStatusDriftReport:
        day = today or datetime.now(UTC).date()
        changes = await self._collect(day)
        written = 0
        for change in changes:
            if not change.needs_write:
                continue
            ok = await self._repository.set_event_status(
                slug=change.slug, status=PleEventStatus.FINISHED
            )
            if not ok:
                # 방금 읽은 행이 쓰기에서 0행이면 그 사이에 사라진 것이다.
                # 조용히 넘기지 않는다.
                raise LookupError(f"대상 행이 사라졌습니다: slug={change.slug!r}")
            written += 1

        logger.info(
            "[kayfabe.event_status] close_past | 대상=%d 반영=%d",
            sum(1 for c in changes if c.needs_write),
            written,
        )
        # **쓰기 전 판정을 그대로 돌려준다.** 다시 읽으면 전부 `already_finished`가
        # 되어, 무엇을 바꿨는지가 응답에서 사라진다.
        return _report(day, changes, written=written)

    async def _collect(self, day: date) -> list[StatusChange]:
        rows = await self._repository.list_event_schedules()
        return [
            StatusChange(
                slug=row.slug,
                status=row.status,
                start_date=row.start_date,
                end_date=row.end_date,
                today=day,
            )
            for row in sorted(rows, key=lambda r: r.slug)
        ]


def _report(
    today: date, changes: list[StatusChange], *, written: int | None = None
) -> EventStatusDriftReport:
    return EventStatusDriftReport(
        today=today,
        items=[
            EventStatusDriftItem(
                slug=change.slug,
                status=change.status,
                start_date=change.start_date,
                end_date=change.end_date,
                verdict=change.verdict,
            )
            for change in changes
        ],
        pending=sum(1 for change in changes if change.needs_write),
        written=written,
    )
