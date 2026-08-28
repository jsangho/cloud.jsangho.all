"""대회 날짜 카탈로그 (Phase 3-12).

**왜 백엔드가 날짜를 따로 들고 있는가.** 지금까지 날짜의 유일한 출처는 프론트의
`www/lib/wwe-ple.ts` `dateLabel` 문자열이었다. 그 값은 화면에만 쓰였으므로 문제가
없었지만, Phase 3-12부터 날짜가 **평가의 시간 게이트**를 좌우한다 — 코퍼스 개정본이
경기보다 앞서는지를 이 날짜로 판정한다. 판정 기준이 프론트 문자열에 매달려 있으면
프론트를 고치는 순간 과거 판정이 조용히 달라진다. 그래서 백엔드가 자기 사본을 갖는다.

`finished_event_results_catalog`과 같은 자리·같은 모양이다: slug를 키로 하는 상수
표이고, 카드 동기화가 지나갈 때 DB에 반영된다.

**여기 없는 대회는 `None`이다.** 날짜가 정해지지 않은 대회(Bad Blood ·
King & Queen of the Ring · Survivor Series)가 실제로 셋 있고, 그 셋은 프론트에서도
`dateLabel: null`이다. `None`은 "모른다"이며 판정 쪽에서 **통과가 아니라 보류**로 읽힌다.

## 값의 출처

- **`summerslam`** — 위키피디아 `SummerSlam_(2026)` 리비전 1367773770의 인포박스
  `date = August 1–2, 2026`으로 확인했다.
- **`money-in-the-bank`** — 위키피디아 `Money_in_the_Bank_(2026)`으로 확인했다.
  2025-10-22에 9월 6일로 발표됐다가 **2026-06-08에 10월 10일로 옮겨졌다**(Phase 3-10).
- **나머지** — 프론트 `dateLabel`에서 옮겨 적었다. 값 자체는 이 저장소가 원래
  갖고 있던 것이지만 **독립 확인은 하지 않았다.** MITB가 몇 달 동안 낡은 9월 6일을
  들고 있었던 전례가 있으므로, 이 대회들의 예측을 채점하기 전에 한 번 확인한다.
"""

from __future__ import annotations

from datetime import date

#: slug → (시작일, 끝날). 하루짜리 대회는 끝날이 `None`이다.
#: 판정이 보는 것은 **시작일 하나**다 — 시작 전 개정본이면 둘째 날 결과도 있을 수 없다.
PLE_EVENT_SCHEDULE: dict[str, tuple[date, date | None]] = {
    "royal-rumble": (date(2026, 1, 31), None),
    "elimination-chamber": (date(2026, 2, 28), None),
    "stand-and-deliver": (date(2026, 4, 4), None),
    "wrestlemania": (date(2026, 4, 18), date(2026, 4, 19)),
    "backlash": (date(2026, 5, 9), None),
    "clash-in-italy": (date(2026, 5, 31), None),
    "night-of-champions": (date(2026, 6, 27), None),
    # 위키 인포박스로 확인함 (리비전 1367773770).
    "summerslam": (date(2026, 8, 1), date(2026, 8, 2)),
    # 위키로 확인함. 9.6 → 10.10 변경분이 반영된 값이다(Phase 3-10).
    "money-in-the-bank": (date(2026, 10, 10), None),
    # bad-blood · king-queen-of-the-ring · survivor-series 는 일정 미정이라 넣지 않는다.
}


def schedule_for(slug: str) -> tuple[date | None, date | None]:
    """모르는 대회면 `(None, None)`. **오늘 날짜로 대신 채우지 않는다.**"""
    start, end = PLE_EVENT_SCHEDULE.get(slug, (None, None))
    return start, end
