from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from kayfabe.app.dtos.event_status_dto import EventStatusDriftReport


class EventStatusUseCase(ABC):
    """대회 `status`와 날짜의 어긋남을 **보여주고**, 요청하면 **닫는다**.

    두 메소드로 갈린 이유는 `close_past_events.py`가 기본 드라이런인 이유와 같다 —
    여기서 `finished`는 사람이 확인한 사실이 아니라 **오늘 날짜로부터 파생된 판정**
    이므로, 보는 것과 쓰는 것이 같은 버튼이면 안 된다.
    """

    @abstractmethod
    async def preview(self, *, today: date | None = None) -> EventStatusDriftReport:
        """아무것도 쓰지 않는다."""
        ...

    @abstractmethod
    async def close_past(self, *, today: date | None = None) -> EventStatusDriftReport:
        """날짜가 지난 대회의 `status`만 `finished`로 넘긴다."""
        ...
