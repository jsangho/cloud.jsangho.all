"""대회 slug → 위키 문서 제목. **사람이 전수 실측한 표다.**

`prediction_knowledge_sources`(허용 도메인)와 같은 자리에 둔다 — 코드가 규칙으로
만들어 낼 수 없고 사람이 확인해야만 아는 값들의 집이다.

## 왜 규칙으로 못 만드는가

위키의 회차 문서 명명이 세 갈래로 갈린다.

    WrestleMania 42                     연도를 안 쓴다
    Backlash (2026)                     `WWE ` 접두사가 빠진다
    Survivor Series: WarGames (2026)    부제가 붙는다 (리다이렉트로 넘어간다)
    NXT Vengeance Day (2026)            NXT 계열은 접두사가 붙는다
    Clash in Italy                      첫 회차라 연도 접미사조차 없다

## 이 표를 쓰는 곳 둘

1. **적재**(`scripts/ingest_event_knowledge.py`) — 근거 문서를 받아 올 주소를 만든다.
2. **결과 확정 에이전트**(`app/use_cases/result_verification_interactor.py`) — 모델에게
   "이 문서를 보라"고 알려 준다. 알려 주지 않으면 모델이 이름을 추측하며 걸음을 태운다:
   `worlds-collide` 실측에서 `Worlds Collide`(동음이의)와 `WWE Worlds Collide`(결과가
   없는 총론)를 거치다 걸음 상한에 걸려 두 경기가 통째로 보류됐다.

**한 벌로 유지한다.** 두 경로가 각자 표를 들면 한쪽만 고친 날 적재와 확정이 다른
문서를 보게 되고, 그때 인용 검증은 통과하는데 근거가 딴 대회의 것이 된다.
"""

from __future__ import annotations

#: **주소가 아니라 제목이고, 총론이 아니라 회차다.** 인코딩은 부르는 쪽이 하고,
#: 실재 여부와 회차는 위키에 물어 확인한다.
#:
#: 값은 2026-09-22에 전수 실측한 것이다.
#:
#: **다음 시즌에 이 표가 낡으면 관문이 소리를 낸다** — 연도가 어긋난 회차 문서는
#: 조용히 통과하지 않고 `wrong_edition`으로 보고된다.
EVENT_ARTICLE_TITLES: dict[str, str] = {
    "royal-rumble": "Royal Rumble (2026)",
    "elimination-chamber": "Elimination Chamber (2026)",
    # NXT 계열은 문서 제목에 `NXT ` 접두사가 붙는다 — 단, `Worlds Collide`는
    # 세 브랜드 합동이라 붙지 않는다. 앱 슬러그에는 접두사를 쓰지 않으므로
    # 여기서만 갈린다.
    "vengeance-day": "NXT Vengeance Day (2026)",
    "stand-and-deliver": "NXT Stand & Deliver (2026)",
    "great-american-bash": "NXT The Great American Bash (2026)",
    "heatwave": "NXT Heatwave (2026)",
    "worlds-collide": "Worlds Collide (2026)",
    "halloween-havoc": "NXT Halloween Havoc (2026)",
    "wrestlemania": "WrestleMania 42",
    "backlash": "Backlash (2026)",
    # **연도 접미사가 없다.** 첫 회차라 문서 제목이 대회 이름 그대로다
    # (2026-05-31 · 토리노 Inalpi Arena, rev 1368715233). `WWE Clash in Italy`로
    # 물으면 `missing`이 나온다 — 그래서 한때 "없는 대회"로 잘못 뺐던 자리다.
    # 회차 관문은 선두 연도 카테고리로 보므로 이 제목도 그대로 통과한다.
    "clash-in-italy": "Clash in Italy",
    "night-of-champions": "Night of Champions (2026)",
    "summerslam": "SummerSlam (2026)",
    "money-in-the-bank": "Money in the Bank (2026)",
    "crown-jewel": "Crown Jewel (2026)",
    "survivor-series": "Survivor Series (2026)",
    "wrestlepalooza": "Wrestlepalooza (2026)",
    # `bad-blood`는 2026 회차가 **없다**(총론 회차 표는 2003·2004·2024 셋뿐).
    # 총론(`WWE Bad Blood`)을 대신 넣지 않는다 — 과거 회차 결과가 적힌 문서라
    # 근거가 아니라 오염이고, 그게 이 관문이 막으려는 바로 그것이다.
    #
    # `king-queen-of-the-ring`은 **`night-of-champions`에 흡수됐다.** 2026년에는
    # 독립 PLE가 아니라 6/1~6/27 토너먼트였고 결승이 거기서 열렸다. 그 경기의
    # 근거 문서는 `Night of Champions (2026)` 하나면 된다 — 토너먼트 문서를 따로
    # 넣으면 같은 경기가 두 문서로 검색된다.
}


def article_title_for(event_slug: str) -> str | None:
    """이 대회의 위키 문서 제목. **모르면 `None`이고, 그것이 정상 상태다.**

    없는 슬러그에 제목을 지어내지 않는다 — `bad-blood`처럼 그 회차가 실재하지 않는
    대회가 있고, 그때 총론 문서를 대신 주면 과거 회차 결과가 근거로 들어온다.
    부르는 쪽은 `None`을 "내가 찾아봐야 한다"로 다룬다.
    """
    return EVENT_ARTICLE_TITLES.get(event_slug)
