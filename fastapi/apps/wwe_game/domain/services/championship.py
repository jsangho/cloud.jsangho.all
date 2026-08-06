"""타이틀 기회 · 브랜드 · 콜업 (2026-08-06 사용자 스펙).

네 가지를 정한다.

1. **기회가 오는가** — 인기도가 높을수록 자주 온다. PLE가 주무대고 TV에서도 가끔 열린다.
2. **어느 벨트인가** — 소속 브랜드에서 인기도로 닿는 가장 높은 벨트.
   그랜드슬램이 한 그룹만 남으면 그쪽 우선.
3. **이겼는가** — 종합점수와 벨트 난도를 견준다.
4. **어디 소속인가** — NXT에서 시작해 콜업되고, 이후 드래프트로 RAW↔스맥다운을 오간다.

**브랜드 이동이 그랜드슬램의 관문이다.** 인터컨티넨탈은 RAW에, US는 스맥다운에 있고
둘 다 필요하므로, 한 브랜드에 머물면 영원히 달성할 수 없다.
"""

from __future__ import annotations

from wwe_game.domain.entities.career_run import CareerRun
from wwe_game.domain.services.seeded_roll import SeededRoll
from wwe_game.domain.value_objects.title import (
    MAIN_ROSTER,
    TITLES,
    Brand,
    Title,
    grand_slam_level,
    missing_groups,
    nxt_titles,
    titles_for_group,
    titles_of,
)

# ── 기회 ─────────────────────────────────────────────────────

SHOT_CHANCE_BASE = 0.06
SHOT_CHANCE_SPAN = 0.40
"""PLE 한 번당 타이틀전이 잡힐 확률 = BASE + SPAN × 인기도/100.

인기도 10이면 10%, 90이면 42%. **인기도가 기회를 만든다**는 결정을 그대로 옮긴 식이다.
"""

TV_SHOT_CHANCE_FACTOR = 0.02
"""주간 TV에서 타이틀전이 열릴 확률은 PLE 한 회의 2%.

**가끔은 RAW·스맥다운에서도 벨트가 오간다**(스펙). 다만 큰 경기는 PLE의 몫이다.

배수를 12%로 잡았다가 낮췄다 — **TV 주차가 PLE보다 12배 많아** 총량이 뒤집힌다.
0.12에서는 커리어당 TV 22.6회 대 PLE 25.3회로 거의 같아져 PLE가 특별할 이유가
없어졌다. 확률이 아니라 **총량**을 기준으로 봐야 하는 지점이었다.
"""

WIN_CHANCE_FLOOR = 0.15
WIN_CHANCE_CEILING = 0.85

REPEAT_REWARD_FACTOR = 0.55
"""이미 감아본 벨트를 다시 딸 때의 보상 배수.

**다섯 번째 월드 타이틀은 첫 번째만큼 사람을 키우지 않는다.** 온전한 보상을 매번 주면
인기도가 치솟아 그랜드슬램이 흔해지고, 0.3까지 낮추면 반대로 월드 임계값에 못 닿는다.
0.4~0.7을 훑어 0.55에서 멈췄다.
"""

TITLE_LOSS_POPULARITY = -3
TITLE_LOSS_IN_RING = -1
"""벨트를 잃으면 명성이 실력보다 크게 깎인다. 두 값은 항상 다르다."""


def title_shot_chance(popularity: int, *, on_tv: bool = False) -> float:
    chance = SHOT_CHANCE_BASE + SHOT_CHANCE_SPAN * (popularity / 100)
    if on_tv:
        chance *= TV_SHOT_CHANCE_FACTOR
    return min(1.0, chance)


# ── 대상 벨트 ────────────────────────────────────────────────


def eligible_titles(run: CareerRun) -> tuple[Title, ...]:
    """소속 브랜드에서 지금 인기도로 도전 가능한 벨트, 1선부터."""
    return tuple(
        t
        for t in titles_of(run.brand, run.identity.gender)
        if run.stats.popularity >= TITLES[t].popularity_required
    )


def grand_slam_chase(run: CareerRun) -> Title | None:
    """그랜드슬램까지 한 그룹 남았고, 그 벨트가 지금 브랜드에서 닿으면 그 벨트."""
    if run.brand not in MAIN_ROSTER:
        return None
    gender = run.identity.gender
    missing = missing_groups(run.titles_won, gender)
    if len(missing) != 1:
        return None
    reachable = [
        t
        for t in titles_for_group(missing[0], gender)
        if run.brand in TITLES[t].brands
        and run.stats.popularity >= TITLES[t].popularity_required
    ]
    return reachable[0] if reachable else None


def target_title(run: CareerRun) -> Title | None:
    """이번 타이틀전의 대상. 없으면 None.

    그랜드슬램 우선이 계층 순서를 덮는다 — 월드 챔피언이 마지막 한 벨트를 주우러
    아래 계층까지 내려가는 그림이 여기서 나온다.
    """
    chase = grand_slam_chase(run)
    if chase is not None:
        return chase
    tiers = eligible_titles(run)
    return tiers[0] if tiers else None


def title_win_chance(score: float, title: Title) -> float:
    edge = (score - TITLES[title].difficulty) / 100
    return max(WIN_CHANCE_FLOOR, min(WIN_CHANCE_CEILING, 0.5 + edge))


# ── 보상 ─────────────────────────────────────────────────────


def reward_of(title: Title, *, first_time: bool = True) -> dict[str, int]:
    spec = TITLES[title]
    factor = 1.0 if first_time else REPEAT_REWARD_FACTOR
    return {
        "popularity": max(1, round(spec.popularity_reward * factor)),
        "in_ring": max(1, round(spec.in_ring_reward * factor)),
    }


def loss_of(title: Title) -> dict[str, int]:
    """계층이 높을수록 잃을 때 더 아프다."""
    rank = {"world": 3, "secondary": 2, "tag": 1}[TITLES[title].tier.value]
    scale = 1 + (rank - 1) * 0.5
    return {
        "popularity": round(TITLE_LOSS_POPULARITY * scale),
        "in_ring": round(TITLE_LOSS_IN_RING * scale),
    }


DEFENSE_REWARD = {"popularity": 2, "in_ring": 1}
"""방어 성공의 소득. **새 대관이 아니므로 이력에 쌓이지 않는다.**

처음엔 방어 승리에도 `award()`를 불렀더니 획득 이력이 계속 늘어 월드 벨트를 커리어당
11.2회 "딴" 것으로 집계됐다(200판 시뮬). 한 번 감고 서른 번 지킨 것과 서른 번 새로
감은 것은 전혀 다른 커리어다.
"""


def award(run: CareerRun, title: Title) -> CareerRun:
    """새 대관. 획득 이력을 **순서대로 쌓는다** (더블 그랜드슬램은 횟수로 판정).

    이미 들고 있는 벨트에는 부르지 않는다 — 그건 방어이지 대관이 아니다.
    """
    if title in run.titles_held:
        return run
    return run.evolve(
        titles_held=run.titles_held | {title},
        titles_won=(*run.titles_won, title),
    )


def strip(run: CareerRun, title: Title) -> CareerRun:
    """방어에 실패해 벨트를 잃는다. **이력은 지우지 않는다.**"""
    return run.evolve(titles_held=run.titles_held - {title})


def slam_level(run: CareerRun) -> int:
    """0 미달 · 1 그랜드슬램 · 2 더블 그랜드슬램."""
    return grand_slam_level(run.titles_won, run.identity.gender)


def is_grand_slam(run: CareerRun) -> bool:
    return slam_level(run) >= 1


# ── NXT 콜업 ─────────────────────────────────────────────────

NXT_CALLUP_POPULARITY = 48
"""NXT 안에서 이만큼 크면 메인 로스터가 부른다."""

CALLUP_POPULARITY_RETENTION = 0.5
"""콜업 때 남는 인기도 비율.

**NXT의 스타덤은 절반만 따라온다.** 그대로 가져오면 콜업 즉시 월드 임계값 근처에 서서
메인 로스터 커리어가 통째로 사라진다. 큰 물에서는 다시 증명해야 한다.
"""


def should_call_up(run: CareerRun) -> bool:
    """NXT 인기도를 채웠거나 NXT 벨트를 모두 감았으면 콜업 (스펙)."""
    if run.brand is not Brand.NXT:
        return False
    if run.stats.popularity >= NXT_CALLUP_POPULARITY:
        return True
    return nxt_titles(run.identity.gender) <= set(run.titles_won)


def call_up(run: CareerRun, roll: SeededRoll) -> CareerRun:
    """메인 로스터로 올린다. NXT 벨트는 반납하고 인기도는 절반이 된다."""
    brand = roll.pick((Brand.RAW, Brand.SMACKDOWN))
    kept = round(run.stats.popularity * CALLUP_POPULARITY_RETENTION)
    return run.evolve(
        brand=brand,
        titles_held=run.titles_held - nxt_titles(run.identity.gender),
        stats=run.stats.evolve(popularity=kept),
    )


# ── 드래프트 ─────────────────────────────────────────────────

DRAFT_INTERVAL_WEEKS = 52
DRAFT_BASE_CHANCE = 0.16
DRAFT_CHASE_CHANCE = 0.70
"""연 1회 드래프트. 평소 16%, **필요한 벨트가 반대 브랜드에 있으면 70%**.

30%로 두었더니 커리어당 12.7회 옮겨 다녀 소속이 의미를 잃었다.

인터컨티넨탈(RAW)과 US(스맥다운)를 둘 다 요구하는 그랜드슬램 규칙 때문에 이동이
막히면 업적이 영영 불가능해진다. 쫓고 있을 때 확률을 올려 길을 열어 둔다.
"""


def other_brand(brand: Brand) -> Brand:
    return Brand.SMACKDOWN if brand is Brand.RAW else Brand.RAW


def wants_transfer(run: CareerRun) -> bool:
    """아직 못 채운 그룹의 벨트가 반대 브랜드에만 있는지."""
    if run.brand not in MAIN_ROSTER:
        return False
    gender = run.identity.gender
    target = other_brand(run.brand)
    for name in missing_groups(run.titles_won, gender):
        group = titles_for_group(name, gender)
        if any(target in TITLES[t].brands for t in group) and not any(
            run.brand in TITLES[t].brands for t in group
        ):
            return True
    return False


def draft(run: CareerRun, roll: SeededRoll) -> CareerRun:
    """드래프트 주차에 브랜드가 바뀔 수 있다. 들고 있던 벨트는 반납한다."""
    if run.brand not in MAIN_ROSTER:
        return run
    chance = DRAFT_CHASE_CHANCE if wants_transfer(run) else DRAFT_BASE_CHANCE
    if not roll.chance(chance):
        return run
    moved = other_brand(run.brand)
    return run.evolve(
        brand=moved,
        titles_held=frozenset(t for t in run.titles_held if moved in TITLES[t].brands),
    )
