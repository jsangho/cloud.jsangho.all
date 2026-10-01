from __future__ import annotations

from abc import ABC, abstractmethod

from kayfabe.app.dtos.event_status_dto import EventScheduleRow


class EventStatusRepository(ABC):
    """`status` 점검이 쓰는 두 가지만 여는 좁은 포트.

    조회용 `PleEventsRepository`에 메소드를 더 얹지 않는 이유는 그쪽이 이미 열두
    개가 넘는 넓은 면이고, 이 기능이 필요한 것은 **읽기 하나와 쓰기 하나**뿐이기
    때문이다. 구현은 같은 PG 어댑터가 겸한다 — 포트가 좁은 것과 어댑터가 하나인
    것은 다른 문제다.
    """

    @abstractmethod
    async def list_event_schedules(self) -> list[EventScheduleRow]:
        """모든 대회의 slug·status·날짜. **카탈로그로 거르지 않는다** —
        `status`는 행의 사실이지 카탈로그의 사실이 아니므로, 화면에서 감춘
        대회(`unlisted`)의 상태도 참이어야 한다.
        """
        ...

    @abstractmethod
    async def set_event_status(self, *, slug: str, status: str) -> bool:
        """`status` 한 칸만 쓴다. 대상 행이 없으면 `False`."""
        ...
