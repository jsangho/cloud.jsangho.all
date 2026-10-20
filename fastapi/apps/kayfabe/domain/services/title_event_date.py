"""타이틀 획득 행의 `won_at` 문자열에서 **대회명과 날짜를 가른다.**

## 왜 파서가 필요한가

`title_acquisitions`에는 **날짜 칸이 없다.** `won_at_slug`가 있어서 `ple_events`로
조인하면 될 것처럼 보이지만, 2026-10-20 운영 실측에서 **388행 전부 `NULL`** 이다 —
그 칸은 우리 2026 픽스처에 있는 대회만 채워지고, 이 표의 대부분은 거기에 없는 과거
대회다(2002~2026, 25개 연도).

날짜는 `won_at` 문자열 안에 있다.

    WrestleMania 25 — April 5, 2009
    No Mercy — October 8, 2007

그래서 **문자열을 갈라야만** 커리어를 연대순으로 읽을 수 있다. 실측 386/388(99%)이
이 꼴이고, 남은 둘은 대회명 없이 날짜만 있다(`June 26, 2026`).

## 지어내지 않는다

날짜를 못 읽으면 `None`이다. 추측해서 넣으면 연대표가 거짓 순서를 말한다 — 그런
행은 화면에서 **맨 뒤로** 보내고 "날짜 미상"으로 적는 쪽이 정직하다.

`em dash`(`—`)와 `hyphen`(`-`) 둘 다 받는다. 위키에서 긁어 온 값이라 표기가 섞여
있을 수 있고, 둘을 가려도 얻는 것이 없다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

#: `April 5, 2009` 꼴. 줄 끝에 붙어 있을 때만 날짜로 본다 — 대회 이름 안에 연도가
#: 들어가는 경우(`WrestleMania 25`)를 날짜로 오인하지 않기 위해서다.
_TAIL = re.compile(r"\s*[—–-]\s*([A-Z][a-z]+ \d{1,2},\s*\d{4})\s*$")

#: 대회명 없이 날짜만 적힌 행. 실측 2건.
_BARE = re.compile(r"^([A-Z][a-z]+ \d{1,2},\s*\d{4})$")

_MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}


@dataclass(frozen=True)
class ParsedTitleEvent:
    """`won_at` 한 줄을 가른 결과."""

    #: 날짜를 떼어낸 대회명. 대회명이 없으면 `None`.
    event_label: str | None
    #: 읽어낸 날짜. 못 읽으면 `None`.
    won_on: date | None


def parse_won_at(won_at: str | None) -> ParsedTitleEvent:
    """`won_at`을 대회명과 날짜로 가른다. **못 읽은 쪽은 `None`이다.**"""
    raw = (won_at or "").strip()
    if not raw:
        return ParsedTitleEvent(event_label=None, won_on=None)

    bare = _BARE.match(raw)
    if bare is not None:
        return ParsedTitleEvent(event_label=None, won_on=_to_date(bare.group(1)))

    tail = _TAIL.search(raw)
    if tail is None:
        # 날짜가 없는 대회명. 그 자체로 정상이므로 이름은 살린다.
        return ParsedTitleEvent(event_label=raw, won_on=None)

    label = raw[: tail.start()].strip()
    return ParsedTitleEvent(event_label=label or None, won_on=_to_date(tail.group(1)))


def _to_date(text: str) -> date | None:
    """`April 5, 2009` → `date(2009, 4, 5)`. 달 이름이 낯설면 `None`."""
    match = re.fullmatch(r"([A-Za-z]+) (\d{1,2}),\s*(\d{4})", text.strip())
    if match is None:
        return None
    month = _MONTHS.get(match.group(1).casefold())
    if month is None:
        return None
    try:
        return date(int(match.group(3)), month, int(match.group(2)))
    except ValueError:
        # `February 30` 같은 값. 지어내지 않고 모른다고 한다.
        return None
