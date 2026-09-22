"""대회 날짜 카탈로그 (Phase 3-12).

**왜 백엔드가 날짜를 따로 들고 있는가.** 지금까지 날짜의 유일한 출처는 프론트의
`www/lib/wwe-ple.ts` `dateLabel` 문자열이었다. 그 값은 화면에만 쓰였으므로 문제가
없었지만, Phase 3-12부터 날짜가 **평가의 시간 게이트**를 좌우한다 — 코퍼스 개정본이
경기보다 앞서는지를 이 날짜로 판정한다. 판정 기준이 프론트 문자열에 매달려 있으면
프론트를 고치는 순간 과거 판정이 조용히 달라진다. 그래서 백엔드가 자기 사본을 갖는다.

`finished_event_results_catalog`과 같은 자리·같은 모양이다: slug를 키로 하는 상수
표이고, 카드 동기화가 지나갈 때 DB에 반영된다.

**여기 없는 대회는 `None`이다.** 날짜가 정해지지 않은 대회(Bad Blood ·
King & Queen of the Ring)가 둘 남아 있고, 그 둘은 프론트에서도 `dateLabel: null`이다.
`None`은 "모른다"이며 판정 쪽에서 **통과가 아니라 보류**로 읽힌다.

**그 둘은 날짜를 몰라서가 아니라 대회가 앱의 주장과 달라서 비어 있다**
(2026-09-22 확인).

- **`bad-blood` — 2026년에 열리지 않는다. 이것이 최종 상태다** (사용자 확인,
  2026-09-22). **데이터로만 남긴다**: `ple_events` 행·경기 5건·예측은 그대로 두고
  화면에서만 뺐다(프론트 `wwe-ple.ts`의 `unlisted: true`). 추후 열릴 수 있어
  지우지 않은 것이며, 되돌리는 것은 그 한 줄을 지우는 일이다.
  **날짜는 영영 비운다.** 위키 총론의 회차 표도 2003·2004·2024 셋뿐이고
  `Bad Blood (2026)`은 없다. 앱의 `bb26-*` 다섯 경기는 `WWE Bad Blood (2024)`
  (2024-10-05 · 애틀랜타)의 카드와 하나씩 일치한다 — 그 다섯에 붙은 예측이
  `ex_post`인 이유가 이것이다. **여기에 날짜를 채워 넣지 말 것.** 열리지 않는
  대회에 날짜를 주면 시간 게이트가 2년 전 경기를 미래 예측처럼 판정한다.
- **`king-queen-of-the-ring` — `night-of-champions`에 흡수됐다** (사용자 확정,
  2026-09-22). 2026년에는 독립 PLE가 아니라 6/1~6/27 토너먼트였고 결승은
  `Night of Champions`(6/27)에서 열렸다. **흡수는 이미 카드에 반영돼 있었다** —
  그 두 경기가 프론트 `night-of-champions`의 `noc26-kotr`·`noc26-qotr`이고,
  위키와도 맞는다(King = Oba Femi · Queen = Iyo Sky). `bad-blood`와 같이
  데이터로만 남기고 화면에서 뺐다(`unlisted: true`).
  **날짜를 넣지 않는다** — 흡수된 대회에 자기 날짜를 주면 같은 경기가 두 대회에
  서로 다른 시각으로 걸린다. 그 경기의 날짜는 `night-of-champions`의 것이다.

## 값의 출처

- **`summerslam`** — 위키피디아 `SummerSlam_(2026)` 리비전 1367773770의 인포박스
  `date = August 1–2, 2026`으로 확인했다.
- **`money-in-the-bank`** — 위키피디아 `Money_in_the_Bank_(2026)`으로 확인했다.
  2025-10-22에 9월 6일로 발표됐다가 **2026-06-08에 10월 10일로 옮겨졌다**(Phase 3-10).
- **`survivor-series`** — 위키피디아 `Survivor Series: WarGames (2026)` 리비전
  1376063302(2026-09-21)의 인포박스 `date = November 28, 2026`으로 확인했다.
  **`ple_events`에 이 대회의 행이 아직 없다** — `apply_event_schedule.py`가
  만들지 않고 exit 1로 알리는 것이 의도된 동작이다.
- **`night-of-champions`** — 아래 "나머지"로 옮겨 적었던 값인데, 2026-09-22에
  `Night of Champions (2026)` 리비전 1375692907의 인포박스 `date = June 27, 2026`과
  **정확히 일치**함을 확인했다.
- **NXT 계열 다섯** — 2026-09-22에 인포박스로 확인했다.
  `NXT Vengeance Day (2026)` 3/7(rev 1374830448) ·
  `NXT The Great American Bash (2026)` 6/28(rev 1366584485) ·
  `NXT Heatwave (2026)` 8/30(rev 1375542249) ·
  `Worlds Collide (2026)` 9/26(rev 1376055676) ·
  `NXT Halloween Havoc (2026)` 10/31(rev 1375893302, 장소는 TBA).
  `stand-and-deliver` 4/4도 같은 날 `NXT Stand & Deliver (2026)`
  리비전 1375463482로 확인했다(미주리 체스터필드).
- **`crown-jewel`** — `Crown Jewel (2026)` 리비전 1372805732의 인포박스
  `date = November 7, 2026`(리야드 Riyadh Season Stadium at KAFD)으로 확인했다.
- **`wrestlepalooza`** — `Wrestlepalooza (2026)` 리비전 1373256857의 인포박스
  `date = December 12, 2026`(퍼스 RAC Arena)으로 확인했다. 북미 밖 개최는 처음이고,
  메인 로스터의 12월 PLE 자체가 2020년 이후 처음이다.
- **`clash-in-italy`** — 같은 날 `Clash in Italy` 리비전 1368715233의 인포박스
  `date = May 31, 2026`(토리노 Inalpi Arena)과 **정확히 일치**함을 확인했다.
  **문서 제목에 연도 접미사가 없다** — 첫 회차라 그렇고, `WWE Clash in Italy`로
  물으면 `missing`이다.
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
    # --- NXT 계열 (2026-09-22 추가, 전부 위키 인포박스로 확인) ---
    "vengeance-day": (date(2026, 3, 7), None),
    "stand-and-deliver": (date(2026, 4, 4), None),
    "great-american-bash": (date(2026, 6, 28), None),
    "heatwave": (date(2026, 8, 30), None),
    "worlds-collide": (date(2026, 9, 26), None),
    "halloween-havoc": (date(2026, 10, 31), None),
    "wrestlemania": (date(2026, 4, 18), date(2026, 4, 19)),
    "backlash": (date(2026, 5, 9), None),
    "clash-in-italy": (date(2026, 5, 31), None),
    "night-of-champions": (date(2026, 6, 27), None),
    # 위키 인포박스로 확인함 (리비전 1367773770).
    "summerslam": (date(2026, 8, 1), date(2026, 8, 2)),
    # 위키로 확인함. 9.6 → 10.10 변경분이 반영된 값이다(Phase 3-10).
    "money-in-the-bank": (date(2026, 10, 10), None),
    # 위키 인포박스로 확인함 (리비전 1372805732). `ple_events`에 행이 아직 없다.
    "crown-jewel": (date(2026, 11, 7), None),
    # 위키 인포박스로 확인함 (리비전 1376063302). `ple_events`에 행이 아직 없다.
    "survivor-series": (date(2026, 11, 28), None),
    # 위키 인포박스로 확인함 (리비전 1373256857). `ple_events`에 행이 아직 없다.
    "wrestlepalooza": (date(2026, 12, 12), None),
    # bad-blood 는 2026년에 열리지 않는다 — 목록에만 남기고 날짜는 영영 비운다.
    # king-queen-of-the-ring 은 대회 대응 관계가 미정이다. 둘 다 위 독스트링 참조.
}


def schedule_for(slug: str) -> tuple[date | None, date | None]:
    """모르는 대회면 `(None, None)`. **오늘 날짜로 대신 채우지 않는다.**"""
    start, end = PLE_EVENT_SCHEDULE.get(slug, (None, None))
    return start, end
