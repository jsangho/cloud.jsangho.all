"""노화. **일괄 하락이 아니다**(사용자 요구 §2).

경험은 쌓이고 몸은 깎인다:

    in_ring    경험으로 **오른다** — 늦게까지 는다
    mic        경험으로 **오른다** — 나이와 거의 무관하다
    stamina    `decline_age` 넘으면 **내린다**
    resilience 더 빨리 내린다 — 회복이 먼저 늦어진다

그래서 40세 선수는 "약한 선수" 가 아니라 **다른 선수**다. 잘하고 말도 잘하지만
쉽게 지치고 늦게 회복한다. 그 조합이 은퇴 위험을 만든다(`career_retirement`).

## 나이는 시즌에서만 오른다

주차 진행이 나이를 건드리지 않는다. 52주가 1년이고, 증가는 시즌 결산 한 곳에서만
일어난다(`career_season.settle`). **멱등 키가 그 호출을 지키므로 결산이 몇 번
재시도되어도 나이는 한 번만 오른다** — 사용자 요구 §2 의 "같은 시즌 종료 이벤트가
중복 실행되어 나이가 두 번 증가하지 않도록 한다" 가 여기서 닫힌다.
"""

from __future__ import annotations

from dataclasses import replace

from kayfabe.domain.services.career_rng import roll
from kayfabe.domain.services.career_world import Ability, Balance, Wrestler


def _growth(wrestler: Wrestler, balance: Balance) -> int:
    """경험치가 오르는 폭. **젊을수록 빠르지만 늙어도 멈추지 않는다.**

    멈추게 하면 노장이 순수 열등이 된다 — 몸만 깎이고 얻는 것이 없으면 긴 커리어를
    고를 이유가 사라진다.
    """
    if wrestler.age < 26:
        return 4
    if wrestler.age < balance.decline_age:
        return 3
    return 1


def _decay(wrestler: Wrestler, balance: Balance) -> int:
    """몸이 깎이는 폭. `decline_age` 이전에는 0이다.

    나이 차에 비례해 커진다 — 34세는 1, 42세는 5쯤이다. 부상 이력이 이걸 가속한다.
    """
    over = wrestler.age - balance.decline_age
    if over <= 0:
        return 0
    base = 1 + over // 2
    return base + wrestler.serious_injuries // 2


def age_one_season(
    wrestler: Wrestler, *, seed: int, balance: Balance, season: int
) -> Wrestler:
    """한 시즌 늙는다. 나이 +1 과 능력치 변화를 **함께** 한다.

    은퇴한 선수는 늙지 않는다 — 기록은 은퇴 당시로 굳어 있어야 한다(§5).
    """
    if wrestler.retired:
        return wrestler

    growth = _growth(wrestler, balance)
    decay = _decay(wrestler, balance)
    # 흔들림을 조금 준다. 같은 나이·같은 선수면 항상 같은 값이다.
    jitter = int(roll(seed, "aging", season, wrestler.name) * 3) - 1

    ability = replace(
        wrestler.ability,
        in_ring=wrestler.ability.in_ring + growth + jitter,
        mic=wrestler.ability.mic + max(1, growth - 1),
        stamina=wrestler.ability.stamina - decay,
        # 회복력이 체력보다 빨리 깎인다. 그래서 "다치면 오래 걸린다" 가 먼저 온다.
        resilience=wrestler.ability.resilience - (decay + (1 if decay else 0)),
    ).clamped()

    return replace(wrestler, age=wrestler.age + 1, ability=ability)


def ability_delta(before: Ability, after: Ability) -> Ability:
    """능력치 변화. 결산 화면이 추이를 적는다(§6 시즌 결산)."""
    return Ability(
        in_ring=after.in_ring - before.in_ring,
        mic=after.mic - before.mic,
        stamina=after.stamina - before.stamina,
        resilience=after.resilience - before.resilience,
    )


def recent_trend(wrestler: Wrestler) -> Ability | None:
    """최근 시즌의 능력치 변화. 시즌이 둘 미만이면 `None`.

    **은퇴 위험이 이 값을 읽는다**(§3.2 "최근 능력치 변화 추이") — 절대 수치보다
    기울기가 중요하다. 체력이 70이어도 급히 떨어지는 중이면 위험하다.
    """
    if len(wrestler.trend) < 2:
        return None
    return ability_delta(wrestler.trend[-2].ability, wrestler.trend[-1].ability)
