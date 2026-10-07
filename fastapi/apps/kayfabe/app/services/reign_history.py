"""보드의 현 재위를 획득 이력에 남기는 규칙 (순수 함수).

## 왜 필요한가

`title_acquisitions`는 손으로 쓴 `REAL_TITLE_ACQUISITIONS`의 거울이었다 — 2026-10-07
운영 실측에서 **367행 전부 `source='real:20'`** 이었고, 보드의 현 재위 24건 중 **21건이
이력에 없었다.** 그래서 벨트 페이지의 획득 횟수가 보드보다 낡은 값을 보였다(실제 사례:
Sami Zayn의 Undisputed WWE가 2회인데 1회로 나왔다 — 9/11 재위가 보드에만 있었다).

현 챔피언이라서 빠진 게 아니다. **카탈로그에 적혔느냐**가 기준이었던 것이고, 그 기준을
보드로 옮기는 것이 여기서 하는 일이다.

## 왜 보드를 기준으로 삼는가

보드 표면은 두 곳에서 온다 — 저장된 `championship_titles`(위키 동기화가 쓴다)와
**읽을 때마다 계산되는** PLE 승계(`apply_results`, 저장되지 않는다). 두 경로에 각각
기록을 심으면 규칙이 두 벌이 된다. 렌더된 보드 하나를 받아 조정하면 **둘 다 덮인다.**

## 한계 — 이것은 스냅샷이지 로그가 아니다

보드는 벨트마다 **현 재위 하나**만 들고 있다. 두 번 돌리는 사이에 벨트가 A → B → C로
옮겨 갔다면 B는 어디에도 안 남는다. 지나간 재위를 복원하려면 위키를 다시 읽어야 하고,
그건 이 함수의 일이 아니다. **빠진 것을 채울 뿐 없는 것을 지어내지 않는다.**

## 중복은 날짜로 막는다, 문자열로 막지 않는다

카탈로그는 `"Night of Champions — June 27, 2026"`, 보드는 `won_at='2026-09-11'` +
`won_event='SmackDown'`으로 같은 사실을 다르게 적는다. 문자열로 대조하면 같은 재위가
두 번 들어간다. **양쪽을 ISO 날짜로 환산해 맞춘다** — 실측에서 카탈로그 367행이 전부
환산됐다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from kayfabe.app.services import belt_lineage

_MONTHS = {
    name: index
    for index, name in enumerate(
        (
            "January February March April May June July August September "
            "October November December"
        ).split(),
        start=1,
    )
}
_MONTH_NAMES = {index: name for name, index in _MONTHS.items()}

#: `"Night of Champions — June 27, 2026"` 안의 날짜. 대회명은 자유 텍스트라 안 믿는다.
_FREE_TEXT_DATE = re.compile(
    r"(January|February|March|April|May|June|July|August|September|October"
    r"|November|December)\s+(\d{1,2}),\s*(\d{4})"
)
_ISO_DATE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")


@dataclass(frozen=True)
class BoardReign:
    """보드가 말하는 현 재위 하나 — 사람 한 명 기준(태그팀은 둘로 펴진다)."""

    competitor_name: str
    belt_name: str
    won_at: str
    """화면에 그대로 나가는 표기. `format_won_at`이 만든다."""
    won_at_date: str
    """ISO. 중복 판정은 이 값으로 한다."""


def won_at_to_date(won_at: str) -> str | None:
    """획득 표기 → ISO 날짜. 못 읽으면 `None`.

    자유 텍스트(`"Payback — June 16, 2013"`)와 ISO(`"2026-09-11"`) 둘 다 받는다 —
    카탈로그와 보드가 같은 사실을 다르게 적기 때문이다.
    """
    iso = _ISO_DATE.match(won_at.strip())
    if iso:
        return iso.group(0)
    found = _FREE_TEXT_DATE.search(won_at)
    if not found:
        return None
    month = _MONTHS[found.group(1)]
    return f"{found.group(3)}-{month:02d}-{int(found.group(2)):02d}"


def format_won_at(won_event: str | None, iso_date: str) -> str:
    """ISO + 대회명 → 카탈로그와 같은 표기.

    **새 형식을 만들지 않는다.** 벨트 상세 화면이 `won_at`을 가공 없이 찍으므로,
    보드에서 온 행만 `2026-09-11`처럼 보이면 같은 목록 안에서 두 형식이 섞인다.
    """
    parsed = _ISO_DATE.match(iso_date)
    if not parsed:
        return iso_date
    year, month, day = (int(part) for part in parsed.groups())
    stamp = f"{_MONTH_NAMES[month]} {day}, {year}"
    event = (won_event or "").strip()
    return f"{event} — {stamp}" if event else stamp


@dataclass(frozen=True)
class ExistingReign:
    """이미 이력에 있는 행. 벨트 이름은 옛 이름일 수 있다."""

    competitor_name: str
    belt_name: str
    won_at: str


def _key(competitor_name: str, belt_name: str, iso_date: str) -> tuple[str, str, str]:
    """중복 판정 키. **벨트는 계보로 접는다** — 옛 이름과 현 이름이 같은 재위다."""
    return (
        competitor_name.strip(),
        belt_lineage.resolve_belt(belt_name) or belt_name,
        iso_date,
    )


def missing_board_reigns(
    *,
    board: list[BoardReign],
    existing: list[ExistingReign],
) -> list[BoardReign]:
    """보드에는 있고 이력에는 없는 재위.

    **날짜를 못 읽은 보드 재위는 내보내지 않는다.** 중복을 막을 키가 없으니 넣으면
    돌릴 때마다 쌓인다 — 빠뜨리는 쪽이 중복보다 고치기 쉽다.
    """
    seen = {
        _key(row.competitor_name, row.belt_name, date)
        for row in existing
        if (date := won_at_to_date(row.won_at)) is not None
    }
    out: list[BoardReign] = []
    for reign in board:
        key = _key(reign.competitor_name, reign.belt_name, reign.won_at_date)
        if key in seen:
            continue
        seen.add(key)  # 같은 실행 안에서도 두 번 넣지 않는다
        out.append(reign)
    return out
