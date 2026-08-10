"""대립 상태 전이 — 서사의 출처 (하네스 §2-D4).

LLM을 쓰지 않기로 한 이 게임에서 **이야기를 만드는 것은 문장 생성기가 아니라 이 상태기계**다.
같은 "경기에서 이겼다"도 무명 상대냐 3년 묵은 숙적이냐에 따라 전혀 다른 사건이 된다.

**되돌아가야 한다.** 무시하면 열기가 식어 내려온다. 한 방향으로만 흐르면 모든 판이
같은 모양이 되고, 대립이 그냥 진행 카운터가 된다.
"""

from __future__ import annotations

from dataclasses import replace

from wwe_game.domain.constants import career_rules as rules
from wwe_game.domain.constants import roster
from wwe_game.domain.constants.career_flags import NEMESIS_LOCKED
from wwe_game.domain.entities.career_run import (
    HEAT_MAX,
    HEAT_MIN,
    CareerRun,
    Rivalry,
    RivalryStage,
)
from wwe_game.domain.services.seeded_roll import SeededRoll

HEAT_HEATED = 35
HEAT_NEMESIS = 70
"""단계 경계. 열기 하나로 단계를 파생한다 — 저장하지 않는다."""

COOL_PER_QUIET_WEEK = 2
"""아무 일도 없는 주차마다 식는 양. **이게 없으면 대립이 영원히 산다.**"""

HEAT_PER_MATCH = 4
HEAT_PER_PLE = 9
HEAT_PER_PROMO = 7
"""무엇이 열기를 올리는가. 빌드업 주차가 경기보다 효율이 좋다 —
대립은 링이 아니라 그 사이에서 쌓인다.
"""

MAX_ACTIVE = 2
"""동시에 유지하는 대립 수. 셋 이상이면 어느 것도 안 뜨거워진다."""

START_CHANCE = 0.06
"""대립이 없을 때 주당 새 대립이 붙을 확률."""

DROP_BELOW = 1
"""이 아래로 식으면 대립을 목록에서 지운다. 끝난 이야기는 들고 있지 않는다."""

BLOWOFF_HEAT_DROP = 58
"""대형 대회에서 숙적과 붙으면 이야기가 끝난다 — 열기가 크게 빠진다.

**이게 없으면 대립이 열기 100에 박혀 영원히 산다.** 한 번 숙적이 된 상대와 30년을
싸우는 셈이라, 새 라이벌이 들어올 자리도 안 생긴다. 실제 대립은 큰 경기 하나로
매듭짓고 각자 다음 이야기로 간다.

완전히 0으로 만들지는 않는다 — 앙금이 남아야 재점화가 이야기가 된다.
"""


def stage_for(heat: int) -> RivalryStage:
    if heat >= HEAT_NEMESIS:
        return RivalryStage.NEMESIS
    if heat >= HEAT_HEATED:
        return RivalryStage.HEATED
    return RivalryStage.INDIFFERENT


def with_heat(rivalry: Rivalry, delta: int) -> Rivalry:
    """열기를 더하고 단계를 다시 계산한다. 단계는 파생값이라 따로 갱신하지 않는다."""
    heat = max(HEAT_MIN, min(HEAT_MAX, rivalry.heat + delta))
    return replace(rivalry, heat=heat, stage=stage_for(heat))


def top_rivalry(run: CareerRun) -> Rivalry | None:
    """가장 뜨거운 대립. 이벤트 조건과 서술 슬롯이 이걸 본다."""
    return max(run.rivalries, default=None, key=lambda r: r.heat)


def pick_rival(run: CareerRun, roll: SeededRoll) -> str | None:
    """급이 맞는 상대를 고른다. 이미 대립 중인 사람은 제외한다.

    **자기 자신도 제외한다** (2026-08-10). 실존 선수를 골라 그 선수가 되는 시스템이라
    (§3-D10-1) 플레이어 이름이 명부에 그대로 있을 수 있고, 그러면 "로만 레인즈가
    로만 레인즈와 대립한다"가 나온다.
    """
    tier = roster.tier_for_popularity(run.stats.popularity)
    taken = {r.rival_name for r in run.rivalries} | {str(run.identity.name)}
    pool = tuple(
        n
        for n in roster.pool_for(run.identity.gender, tier, run.week)
        if n not in taken
    )
    return roll.pick(pool) if pool else None


def pick_opponent(run: CareerRun, roll: SeededRoll) -> str | None:
    """그 주차 경기의 상대 (2026-08-10 사용자 요청).

    **대립 중인 상대가 먼저다.** 몇 주째 쌓아 온 이야기가 있는데 엉뚱한 사람과 붙으면
    그 대립은 화면에서 사라진다. 대립이 없을 때만 급이 맞는 명부에서 뽑는다.
    """
    hot = top_rivalry(run)
    if hot is not None:
        return hot.rival_name
    return pick_rival(run, roll)


def start_rivalry(run: CareerRun, week: int, roll: SeededRoll) -> Rivalry | None:
    """새 대립을 연다. 자리가 없거나 상대가 없으면 None."""
    if len(run.rivalries) >= MAX_ACTIVE:
        return None
    name = pick_rival(run, roll)
    if name is None:
        return None
    return Rivalry(
        rival_name=name,
        stage=RivalryStage.INDIFFERENT,
        heat=HEAT_PER_PROMO,
        started_week=week,
    )


def advance_rivalries(
    run: CareerRun,
    week: int,
    heat_gain: int,
    roll: SeededRoll,
    *,
    blowoff: bool = False,
) -> tuple[Rivalry, ...]:
    """한 주차분 전이. 가장 뜨거운 대립만 달아오르고 나머지는 식는다.

    열기를 골고루 나눠 주면 셋 다 미지근해진다. 이야기는 하나씩 집중돼야 커진다.

    `blowoff`는 대형 대회 주차다 — 숙적 단계라면 거기서 이야기를 매듭짓는다.
    """
    hottest = top_rivalry(run)
    settled = blowoff and hottest is not None and hottest.stage is RivalryStage.NEMESIS
    moved: list[Rivalry] = []
    for rivalry in run.rivalries:
        is_top = hottest is not None and rivalry.rival_name == hottest.rival_name
        if is_top and settled:
            delta = -BLOWOFF_HEAT_DROP  # 큰 경기로 매듭지었다
        elif is_top:
            delta = heat_gain
        else:
            delta = -COOL_PER_QUIET_WEEK
            if NEMESIS_LOCKED in run.flags:
                # 매듭짓지 못한 대립은 한 주 쉰다고 식지 않는다 (§3-D26).
                delta = -round(COOL_PER_QUIET_WEEK * rules.NEMESIS_LOCK_COOL_FACTOR)
        nxt = with_heat(rivalry, delta)
        if nxt.heat >= DROP_BELOW:
            moved.append(nxt)

    if not moved and roll.chance(START_CHANCE):
        fresh = start_rivalry(run, week, roll)
        if fresh is not None:
            moved.append(fresh)
    elif len(moved) < MAX_ACTIVE and roll.chance(START_CHANCE / 2):
        fresh = start_rivalry(run.evolve(rivalries=tuple(moved)), week, roll)
        if fresh is not None:
            moved.append(fresh)

    return tuple(moved)
