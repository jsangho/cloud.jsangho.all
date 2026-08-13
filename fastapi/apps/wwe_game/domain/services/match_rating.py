"""그 경기가 어땠나 — 별점 (하네스 §3-D56).

이 게임에는 지금까지 **"좋은 밤"이라는 축이 없었다.** 승패와 벨트는 있었지만, 프로레슬링
팬이 한 밤을 기억하는 방식 — *그 경기 몇 점짜리였지* — 를 말할 수단이 없었다. 30년을
지나온 로그에서 "5년차 레슬매니아 그 경기"를 짚을 근거가 없다는 뜻이다.

## 저장하지 않는다

`title_scene`(§3-D38) · `show_card`(§3-D52)와 같은 자리다. 별점은 **값이 아니라 보는
방식**이라(§3-D45), 그 밤의 재료로 매번 되짚는다. 로그 행에 이미 있는 것들 — 경기력,
상대의 급, 형식, 걸린 벨트, 대회의 크기 — 이 재료의 전부다.

## 판정이 아니다

별점은 승패에 **아무 영향도 주지 않는다.** 경기 결과는 §3-D1이 정한 대로 도메인의 판정
함수가 먼저 정하고, 별점은 그 결과를 나중에 읽어 매긴다. 반대로 두면 "별 다섯을 노려
지는 쪽이 유리한" 최적해가 생기고, 그건 §11-14가 막는 종류의 것이다.
"""

from __future__ import annotations

from typing import Final

from wwe_game.domain.constants.roster import RivalTier
from wwe_game.domain.services import seeded_roll
from wwe_game.domain.services.seeded_roll import SeededRoll

MAX_STARS: Final = 7.0
"""별점의 상한 — **다섯을 넘길 수 있다** (2026-08-12 사용자 요청).

프로레슬링 평자들이 전설적인 경기에 별 다섯 이상을 주는 관행 그대로다. 다만 그 자리는
아무 밤에나 열리지 않는다 — 아래 `CLASSIC_*`이 조건과 빈도를 잡는다.
"""
STEP: Final = 0.25
"""별점의 눈금. 프로레슬링 평자들이 쓰는 4분의 1 단위를 그대로 쓴다."""

BASE: Final = 0.8
"""아무 조건이 없는 경기의 바닥. **평범한 밤은 평범하게 읽혀야 한다.**

처음엔 2.0으로 잡았다가 내렸다 — 그 값이면 30년 2854경기의 **평균이 4.63이고 별 다섯이
39.6%**였다. 별 다섯이 흔하면 별점은 아무 말도 하지 않는다. 지금은 평범한 중간급 경기가
2점대에 앉고, 별 다섯은 좋은 선수·큰 무대·걸린 벨트가 겹친 밤에만 나온다.
"""

RING_WEIGHT: Final = 2.0
"""경기력(0~100)이 별점에 얹는 최대치. 실력이 가장 큰 몫이지만 혼자 별 다섯을 만들지는
못한다 — 무대와 상대가 나머지를 준다."""

STAGE_BONUS: Final[dict[str, float]] = {"major": 0.45, "ple": 0.28, "special": 0.12}
"""무대가 주는 몫. **같은 경기도 레슬매니아에서 더 크게 읽힌다** — 관중과 준비 기간이
다르기 때문이고, 이 게임의 서술도 이미 그렇게 말한다(§3-D21-1)."""

TITLE_BONUS: Final = 0.35
"""벨트가 걸린 경기. 걸린 것이 있으면 경기가 달라진다."""

TIER_BONUS: Final[dict[RivalTier, float]] = {
    RivalTier.PROSPECT: 0.0,
    RivalTier.MIDCARD: 0.18,
    RivalTier.MAIN_EVENT: 0.35,
}
"""상대의 급. 좋은 상대가 좋은 경기를 만든다 — 혼자 하는 경기는 없다."""

FEUD_BONUS: Final = 0.3
"""쌓인 대립의 결착 (§3-D66). **이야기가 있는 경기가 더 좋은 경기다** — 이 게임의
전제인데(§3-D44) 별점은 그걸 안 보고 있었다."""

STIPULATION_BONUS: Final = 0.2
"""특수 경기. 철창과 사다리는 그 자체로 이야기를 만든다."""

NOISE: Final = 0.7
"""같은 조건이어도 밤마다 다르게 나오는 폭.

**이게 없으면 별점이 스탯의 다른 표기가 된다.** 실제로도 같은 둘이 붙어도 어떤 밤은
명경기가 되고 어떤 밤은 아니다 — 그 흔들림이 별점을 볼 이유다.
"""


CLASSIC_GATE: Final = 3.6
"""명경기 굴림이 열리는 문턱. **이미 좋은 경기에서만 열린다** — 평범한 밤이 갑자기
전설이 되면 별점이 다시 무의미해진다."""

CLASSIC_CHANCE: Final = 0.06
CLASSIC_BONUS: Final[tuple[float, float]] = (0.75, 2.25)
"""문턱을 넘은 경기가 명경기가 될 확률과 그때 얹히는 몫.

30년에 몇 번이면 된다. 흔하면 "전설"이라는 말이 값을 잃고, 아예 없으면 30년을 지나도
기억에 남는 밤이 하나도 없다.
"""


def rate(
    seed: int,
    week: int,
    *,
    in_ring: int,
    rival_tier: RivalTier = RivalTier.MIDCARD,
    stage: str | None = None,
    has_title: bool = False,
    has_stipulation: bool = False,
    has_feud: bool = False,
    salt: str = "",
) -> float:
    """0.0~`MAX_STARS` 별점, 0.25 단위. 같은 밤은 언제 물어도 같은 별점이다 (§3-D4).

    **주석이 "0.0~5.0"이었다** (2026-08-13 정정). 상한은 처음부터 7.0이었고 실측에서
    5.5★·6.0★가 실제로 나온다(13,226경기 중 11건). 멜처가 5점을 넘겨 주기 시작한
    뒤로는 그쪽이 맞는 척도라 **코드가 옳고 주석이 낡았다** — 주석을 고쳤다.

    `stage`는 `major`·`ple`·`special` 중 하나이거나 None(주간 방송)이다.
    `salt`는 한 밤에 여러 경기가 설 때 그것들을 갈라 주는 열쇠다 — 없으면 같은 주차의
    모든 경기가 똑같이 흔들린다.
    """
    roll = SeededRoll(seed, week, f"{seeded_roll.RATING}:{salt}")
    score = BASE
    score += RING_WEIGHT * (max(0, min(100, in_ring)) / 100)
    score += STAGE_BONUS.get(stage or "", 0.0)
    score += TITLE_BONUS if has_title else 0.0
    score += TIER_BONUS[rival_tier]
    score += STIPULATION_BONUS if has_stipulation else 0.0
    score += FEUD_BONUS if has_feud else 0.0
    score += roll.uniform(-NOISE, NOISE)
    if score >= CLASSIC_GATE and roll.chance(CLASSIC_CHANCE):
        # 그 밤이 전설이 됐다. **좋은 경기에서만 열리는 문**이다.
        score += roll.uniform(*CLASSIC_BONUS)
    return _to_quarter(score)


def _to_quarter(score: float) -> float:
    """0.25 눈금으로 접고 0~`MAX_STARS`에 가둔다."""
    clamped = max(0.0, min(MAX_STARS, score))
    return round(clamped / STEP) * STEP
