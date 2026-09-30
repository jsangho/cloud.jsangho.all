"""참가자가 **사람이 아닌** 경기들. 자동 예측이 건너뛸 대상이다.

`ple_match_id_prefixes`와 같은 자리 — 코드가 규칙으로 만들 수 없고 사람이 대조해야만
아는 값들의 집이다.

## 무엇이 문제인가

위키는 대진이 정해지기 전에도 **형식**을 먼저 싣는다.

    Raw's World Heavyweight Champion vs. SmackDown's Undisputed WWE Champion

자리는 둘이고 경기도 실재하는데, 그 자리에 설 사람은 대회 당일 그 벨트를 든 사람이라
아직 아무도 모른다. 위키가 적은 그대로 두는 것이 맞다 — 이름을 지어 넣으면 확정되지
않은 것이 확정된 것처럼 보인다.

**그러나 여기에 예측을 만들면 안 된다.** 만들면 `pick_name`이 사람이 아니라 역할명이
되고, 나중에 위키가 실명을 채우는 순간 경기 id가 통째로 달라져 그 예측이 **고아**가
된다. 실제로 그렇게 생긴 고아를 하나 지운 적이 있다(2026-09-30, `mitb26-ic`).

## `미정` 칸과 다르다

픽스처에는 이미 미정 표시가 있다(`BRACKET_LABELS.tbd`). 6인 래더의 빈 자리 하나가
그것인데, 그런 경기는 **확정된 참가자가 다섯 있으므로** 예측이 성립한다. 여기 적는
것은 자리가 **전부** 미확정인 경기다.

## 이름을 함께 적는 이유

표만 두면 조용히 낡는다. 위키가 실명을 채우고 픽스처가 갱신되면 이 항목은 더 이상
사실이 아닌데, 그때도 스크립트는 계속 건너뛴다 — 그러면 그 대회는 영영 예측이 안
생기고 아무도 이유를 모른다.

그래서 **그때 픽스처에 적혀 있던 이름을 함께 박아 둔다.** 이름이 달라지면
`test_unconfirmed_match_cards.py`가 실패하고, 사람이 이 표에서 그 줄을 지우게 된다.
`ple_match_id_prefixes`가 픽스처와 대조되는 것과 같은 장치다.
"""

from __future__ import annotations

#: 대회 slug → {경기 id: 그때 픽스처에 적혀 있던 참가자 이름들}.
#: 값은 2026-09-30에 `www/lib/wwe-ple-matches.ts`에서 확인했다.
UNCONFIRMED_MATCH_CARDS: dict[str, dict[str, tuple[str, ...]]] = {
    # Crown Jewel(2026-11-07)은 두 브랜드 챔피언끼리 붙이는 형식이다. 11/7에 그
    # 벨트를 든 사람이 나가므로 위키도 아직 모른다.
    "crown-jewel": {
        "cj26-crown-jewel": (
            "Raw's World Heavyweight Champion",
            "SmackDown's Undisputed WWE Champion",
        ),
        "cj26-women-crown-jewel": (
            "Raw's Women's World Champion",
            "SmackDown's WWE Women's Champion",
        ),
    },
}


def unconfirmed_match_keys(event_slug: str) -> frozenset[str]:
    """이 대회에서 참가자가 미확정인 경기 id들. 없으면 빈 집합이다."""
    return frozenset(UNCONFIRMED_MATCH_CARDS.get(event_slug, {}))
