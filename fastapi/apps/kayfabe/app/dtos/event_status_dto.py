"""대회 `status` 드리프트 점검의 입출력 DTO."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class EventScheduleRow:
    """판정에 필요한 `ple_events` 한 행. **날짜는 DB에서 읽는다 — 카탈로그가 아니다.**

    판정 기준이 카탈로그에 매달려 있으면 카탈로그를 고치는 순간 `status`와 시간
    게이트가 서로 다른 날짜를 보게 된다.
    """

    slug: str
    status: str
    start_date: date | None
    end_date: date | None


@dataclass(frozen=True)
class EventStatusDriftItem:
    """대회 하나의 판정 결과. `verdict`는 도메인이 고른 한 단어다."""

    slug: str
    status: str
    start_date: date | None
    end_date: date | None
    verdict: str


@dataclass(frozen=True)
class EventStatusDriftReport:
    """점검 결과 전체.

    `written`은 **쓰기를 한 경우에만** 숫자가 들어간다. 미리보기에서 0을 넣으면
    "아무것도 쓸 게 없었다"와 "쓰지 않았다"가 같은 모양이 된다.
    """

    today: date
    items: list[EventStatusDriftItem]
    pending: int
    written: int | None = None
