"""대회 slug → 경기 id 접두사. **사람이 확인한 표다.**

`wiki_event_titles`·`wiki_belt_names`와 같은 자리 — 코드가 규칙으로 만들 수 없고
사람이 대조해야만 아는 값들의 집.

## 왜 규칙으로 못 만드는가

실측하면 네 갈래다.

    wrestlemania    → wm42     연도가 아니라 **회차**다
    stand-and-deliver → sad26  머리글자 셋
    clash-in-italy  → italy26  머리글자가 아니라 **한 낱말**
    backlash        → bl26     두 글자

슬러그에서 유도하면 전부 틀린다.

## 이 표는 **폴백이다**

접두사의 정본은 픽스처에 이미 있는 경기 id다(`ple_fixture_file.id_prefix_of`).
이 표는 **경기가 0건이라 읽을 자리가 없을 때만** 쓴다 — 대진이 아직 발표되지 않은
대회가 그렇다. 둘이 어긋나면 픽스처가 이긴다. 그 어긋남은 테스트가 잡는다
(`test_ple_match_id_prefixes.py`).

## `ss26`은 둘이 나눠 쓴다

SummerSlam(`ss26-n1-*`·`ss26-n2-*`)과 Survivor Series(`ss26-*`)가 같은 접두사를
쓴다. 경기 id는 **대회 안에서만 유일하면 되므로**(DB의 `match_key`가 대회에
종속된다) 고장이 아니다. 고치려고 한쪽을 바꾸면 이미 저장된 예측이 그 경기를
잃는다 — 그대로 둔다.
"""

from __future__ import annotations

#: 값은 2026-09-29에 `www/lib/wwe-ple-matches.ts`에서 전수 확인했다.
#: 새 대회를 픽스처에 넣을 때 여기도 한 줄 더한다.
PLE_MATCH_ID_PREFIXES: dict[str, str] = {
    "royal-rumble": "rr26",
    "elimination-chamber": "ec26",
    "vengeance-day": "vd26",
    "stand-and-deliver": "sad26",
    "great-american-bash": "gab26",
    "heatwave": "hw26",
    "worlds-collide": "wc26",
    # 대진 미발표 — 이 표가 **실제로 쓰이는 유일한 자리**다. 경기가 0건이라
    # 픽스처에서 접두사를 읽을 수 없다.
    "halloween-havoc": "hh26",
    "wrestlemania": "wm42",
    "backlash": "bl26",
    "clash-in-italy": "italy26",
    "night-of-champions": "noc26",
    "summerslam": "ss26",
    "money-in-the-bank": "mitb26",
    "crown-jewel": "cj26",
    "survivor-series": "ss26",
    # 대진 미발표 — `halloween-havoc`과 같은 자리다.
    "wrestlepalooza": "wp26",
}


def id_prefix_for(event_slug: str) -> str | None:
    """이 대회의 경기 id 접두사. **모르면 `None`이고, 그것이 정상 상태다.**

    지어내지 않는다 — 틀린 접두사로 만든 id는 기존 경기와 안 맞아서, 동기화가
    그 경기를 "새 경기"로 보고 옛 행을 지운다.
    """
    return PLE_MATCH_ID_PREFIXES.get(event_slug)
