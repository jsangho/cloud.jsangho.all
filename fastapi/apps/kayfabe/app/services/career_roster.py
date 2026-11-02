"""커리어 세계의 실제 로스터. **실제 WWE 현역을 게임 선수로 옮긴다.**

## 무엇이 실제이고 무엇이 게임 값인가

| 칸 | 출처 |
|---|---|
| 이름 · 브랜드 | DB `wrestlers` (운영 명부) |
| 나이 | DB `birth_date` — 없으면 30세로 둔다 |
| 스타일 | 로스터 카탈로그의 **실제 몸무게** — 무거우면 파워, 가벼우면 하이플라이어 |
| 남자부 / 여자부 | `career_divisions.WOMEN` (사람이 검토하는 명단) |
| 인기도 · 기술 · 마이크 | **실제 타이틀 획득 이력**(`title_acquisitions`)과 경력 연차로 계산한 **게임용 추정치** |
| 체력 · 회복력 | 나이로 계산한 게임용 추정치 |
| 전적 | **0승 0패에서 시작한다** — 실제 경기 승패는 쓰지 않는다(2026-11-02 사용자 결정) |
| 성향(선역/악역) | DB 에 없다. 이름에서 결정론으로 정한 **게임 설정**이다 |

추정치는 근거가 있는 값이지 측정값이 아니다. 화면은 이 숫자를 "실제 능력치" 로
부르지 않는다.

## 브랜드

세계는 NXT · Raw · SmackDown 셋으로 돈다. Free Agent · Evolve 는 넣지 않는다 —
로스터 카탈로그도 Evolve 를 뺀다(`wwe_roster_catalog.ROSTER_SOURCE`).
"""

from __future__ import annotations

import zlib
from collections import Counter
from collections.abc import Iterable, Mapping
from datetime import date
from typing import Literal

from kayfabe.app.services.career_divisions import WOMEN
from kayfabe.app.services.data_center_stats import TitleRow, WrestlerRow
from kayfabe.app.services.wwe_roster_catalog import RETAINED_FOR_RECORDS, RosterEntry
from kayfabe.domain.services.career_world import (
    Ability,
    AbilitySnapshot,
    Alignment,
    Title,
    Wrestler,
)

Division = Literal["men", "women"]

#: DB 브랜드(CSV 구역 머리 그대로) → 세계 브랜드. 여기 없는 값은 세계에 넣지 않는다.
_BRAND = {"RAW": "Raw", "SMACKDOWN": "SmackDown", "NXT": "NXT"}

#: 주요 벨트로 치는 이름 조각. 인기도에 더 크게 들어간다.
_MAJOR_BELT_MARKERS = (
    "World",
    "WWE Championship",
    "Undisputed",
    "WWE Women's Championship",
)

#: 브랜드마다 이만큼은 있어야 대진이 성립한다. 모자라면 실제 로스터를 쓰지 않는다.
MIN_PER_BRAND = 2

#: 나이를 모르는 선수의 나이.
_UNKNOWN_AGE = 30


def women_titles() -> tuple[Title, ...]:
    """여자부 세계의 벨트 넷. 사다리(요구 인기도)는 남자부 기본값과 같다."""
    return (
        Title(name="NXT Women's Championship", brand="NXT", required_popularity=40),
        Title(
            name="Women's Intercontinental Championship",
            brand="Raw",
            required_popularity=65,
        ),
        Title(
            name="WWE Women's Championship", brand="SmackDown", required_popularity=85
        ),
        Title(
            name="Women's Tag Team Championship", brand="Raw", required_popularity=50
        ),
    )


def division_of(name: str) -> Division:
    return "women" if name in WOMEN else "men"


def _clamp(value: float, low: int, high: int) -> int:
    return max(low, min(high, round(value)))


def _age(birth_date: str | None, today: date) -> int | None:
    """`YYYY-MM-DD`. 달·일이 `??` 인 행은 해만 쓴다. 해석이 안 되면 `None`."""
    if not birth_date:
        return None
    parts = birth_date.strip().split("-")
    try:
        year = int(parts[0])
    except (ValueError, IndexError):
        return None
    try:
        month, day = int(parts[1]), int(parts[2])
    except (ValueError, IndexError):
        return today.year - year
    return today.year - year - ((today.month, today.day) < (month, day))


def _style(weight_kg: float | None, division: Division) -> str:
    """실제 몸무게로 스타일을 정한다. 기준은 부마다 다르다."""
    if weight_kg is None:
        return "테크니션"
    heavy, light = (115, 85) if division == "men" else (80, 58)
    if weight_kg >= heavy:
        return "파워"
    if weight_kg <= light:
        return "하이플라이어"
    return "테크니션"


def _is_major(belt: str) -> bool:
    return any(marker in belt for marker in _MAJOR_BELT_MARKERS)


def to_wrestler(
    *,
    name: str,
    brand: str,
    age: int | None,
    weight_kg: float | None,
    titles: int,
    major_titles: int,
    division: Division,
) -> Wrestler:
    """실제 선수 한 명 → 게임 선수. **순수 함수다** — 같은 입력이면 같은 선수다."""
    years = age if age is not None else _UNKNOWN_AGE
    exp = max(0, min(20, years - 20))
    t, m = min(titles, 8), min(major_titles, 5)
    main_roster = brand != "NXT"
    popularity = _clamp(25 + 5 * t + 6 * m + (10 if main_roster else 0), 15, 95)
    in_ring = _clamp(45 + 1.2 * exp + 2 * t + 3 * m, 35, 92)
    ability = Ability(
        in_ring=in_ring,
        mic=_clamp(in_ring - 8 + (6 if m > 0 else 0), 30, 90),
        stamina=_clamp(85 - max(0, years - 30) * 1.5, 45, 90),
        resilience=_clamp(80 - max(0, years - 33) * 1.5, 40, 88),
    )
    # 성향은 DB 에 없다 — 이름에서 결정론으로. 셋 중 하나가 악역(기본 로스터와 같은 비율).
    heel = zlib.crc32(name.encode("utf-8")) % 3 == 0
    return Wrestler(
        name=name,
        style=_style(weight_kg, division),
        brand=brand,
        age=years,
        debut_age=max(18, years - exp),
        alignment=Alignment.HEEL if heel else Alignment.FACE,
        popularity=popularity,
        ability=ability,
        trend=(AbilitySnapshot(season=1, age=years, ability=ability),),
    )


def build_roster(
    *,
    rows: Iterable[WrestlerRow],
    catalog: Mapping[str, RosterEntry],
    acquisitions: Iterable[TitleRow],
    division: Division,
    today: date,
) -> tuple[Wrestler, ...] | None:
    """운영 명부 → 세계 로스터. **브랜드마다 `MIN_PER_BRAND` 가 안 되면 `None`.**

    `None` 이면 호출자가 기본(가상) 로스터로 돌아간다 — 명부를 못 읽은 채로
    한두 명짜리 세계를 만들면 대진이 서지 않는다.
    """
    held = Counter(a.competitor_name for a in acquisitions)
    major = Counter(a.competitor_name for a in acquisitions if _is_major(a.belt_name))
    out: list[Wrestler] = []
    for row in rows:
        # 카탈로그 키와 같은 정리(공백만) — `competitor_roster.normalize_name`.
        name = " ".join(row.name.split())
        brand = _BRAND.get((row.brand or "").strip().upper())
        if brand is None or name in RETAINED_FOR_RECORDS:
            continue
        if division_of(name) != division:
            continue
        entry = catalog.get(name)
        out.append(
            to_wrestler(
                name=name,
                brand=brand,
                age=_age(row.birth_date, today),
                weight_kg=entry["weight_kg"] if entry else None,
                titles=held[name],
                major_titles=major[name],
                division=division,
            )
        )
    per_brand = Counter(w.brand for w in out)
    if any(per_brand[b] < MIN_PER_BRAND for b in _BRAND.values()):
        return None
    # 인기도 높은 순 — 세계관 탭이 이 순서로 그린다.
    return tuple(sorted(out, key=lambda w: (-w.popularity, w.name)))
