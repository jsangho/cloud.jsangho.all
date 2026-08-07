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

from wwe_game.domain.constants import career_rules as rules
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
from wwe_game.domain.value_objects.week_report import CallUpReason

# ── 기회 ─────────────────────────────────────────────────────

SHOT_CHANCE_BASE = 0.016
SHOT_CHANCE_SPAN = 0.108
"""대회 한 번당 타이틀전이 잡힐 확률 = BASE + SPAN × 인기도/100.

인기도 10이면 2.7%, 90이면 11.3%. **인기도가 기회를 만든다**는 결정을 그대로 옮긴 식이다.

**0.06/0.40에서 내렸다**(2026-08-07, §3-D21-1). 대회가 연 4회에서 11회로 늘자 커리어당
타이틀전이 47회에서 149회로 뛰었고, 그랜드슬램이 25%에서 75%로 튀었다. 회당 확률을
낮춰 총량을 되돌린다 — **바뀐 것은 달력이지 벨트의 무게가 아니다.** 같은 시드 60판에서
타이틀전 42.4회 · 그랜드슬램 25% · 완주 93%로, 개정 전(47.3 · 25% · 92%)과 맞는다.
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


def title_shot_chance(
    popularity: int,
    *,
    on_tv: bool = False,
    major: bool = False,
    special: bool = False,
) -> float:
    """이번 무대에서 벨트가 걸릴 확률.

    대회가 연 4회에서 13회로 늘면서 회당 확률을 낮췄다(§3-D21-1) — 총량을 지키려면
    그래야 하지만, 그러면 큰 대회도 밋밋해진다. **급으로 다시 벌린다.**
    """
    chance = SHOT_CHANCE_BASE + SHOT_CHANCE_SPAN * (popularity / 100)
    if major:
        chance *= rules.MAJOR_SHOT_MULTIPLIER
    if special:
        chance *= rules.SPECIAL_SHOT_FACTOR
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


GRAND_SLAM_CHASE_CHANCE = 0.015
"""**타이틀전 한 번당** 마지막 한 그룹을 주우러 아래 계층으로 내려갈 확률.

**보장이던 것을 확률로 바꿨다.** 항상 내려가게 두었더니 그랜드슬램이 난도가 아니라
**생존**으로 정해졌다 — 30년을 완주하기만 하면 이 규칙이 남은 한 벨트까지 데려다줘서
부상을 피하는 플레이의 달성률이 **97%**였다(150판). 벨트 난도를 +20 해도 93%로
꿈쩍하지 않았고, 타이틀전 빈도를 4분의 1로 줄여야 44%가 되는데 그때는 커리어당 대관이
13회에서 4회로 무너져 타이틀 게임 자체가 사라졌다. 원인이 수치가 아니라 구조였다.

**값이 작아 보이는 것은 기회가 많아서다.** 한 그룹만 남은 상태로 커리어 후반 20~30번의
타이틀전을 치르므로, 1.5%라도 판을 거듭하면 4분의 1쯤은 결국 걸린다. 0.08만 돼도
계산적 플레이가 46%로 되돌아간다 — 회당 확률이 아니라 **누적**으로 봐야 하는 자리다.

내려가는 그림 자체는 §3-D20의 결정이라 지우지 않고 **드물게** 만들었다. 마지막 한 벨트는
이제 사무실이 언제 그 카드를 잡아 주느냐에 달렸고, 그래서 커리어마다 갈린다. 대관 횟수는
건드리지 않았다(커리어당 14.4회 유지) — 줄어든 것은 트로피이지 경기가 아니다.
"""


def target_title(run: CareerRun, roll: SeededRoll) -> Title | None:
    """이번 타이틀전의 대상. 없으면 None.

    그랜드슬램 우선이 계층 순서를 덮되, **굴림에 걸렸을 때만** 덮는다. 안 걸리면 평소대로
    계층 1선이 잡히고 — 대개 이미 감아 본 벨트다 — 그 기회는 그냥 지나간다.
    """
    chase = grand_slam_chase(run)
    if chase is not None and roll.chance(GRAND_SLAM_CHASE_CHANCE):
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

NXT_MIN_WEEKS = 78
"""이 주차 전에는 실력으로 올라갈 수 없다 — **1.5년**.

덱이 들어오기 전에는 필요 없던 하한이다. 이벤트가 실제로 뜨기 시작하자 NXT 구간이
80주 남짓으로 줄면서 **6개월 만에 올라가는 커리어**가 나왔다(200판 실측 최단 0.5년).
NXT가 한 챕터로 읽히려면 최소 한 시즌은 굴러야 한다.

**깜짝 콜업은 이 하한을 넘어선다**(§3-D22-1) — 그게 '깜짝'인 이유다.
"""

NXT_PATIENCE_WEEKS = 260
"""이 주차에 문턱이 최저가 된다 — **5년**. 그 뒤로는 더 내려가지 않는다.

기울기를 정하는 값이지 종착점이 아니다. 208주(4년)로 두면 문턱이 빨리 내려앉아 **늦게
크는 커리어까지 3년 안에 전부 올라갔다**(150판 최장 3.0년). 260주로 늘리자 같은 잔류율
(계산적 2% · 무작위 19%)에서 꼬리만 3.6년까지 벌어졌다 — 목표한 1.5~4년 폭이 여기서 나온다.
"""

NXT_CALLUP_POPULARITY_EARLY = 76
"""하한(1.5년) 시점의 콜업 문턱. 이 나이에 올라가려면 NXT를 압도해야 한다."""

NXT_CALLUP_POPULARITY_LATE = 30
"""인내 만료(5년) 시점의 콜업 문턱.

**문턱이 재적 기간에 따라 내려간다.** 고정값 하나로 두면 커리어가 전부 같은 인기도에서
같은 시기에 올라가 NXT 구간이 판마다 똑같아진다. 내려가는 문턱은 두 가지를 동시에
만든다 — 빨리 큰 선수는 일찍 올라가되 **높은 인기도를 들고 가고**(76×0.42), 더디 큰
선수는 늦게 올라가되 **바닥에서 다시 시작한다**(30×0.42). 같은 규칙 하나에서 스타와
저니맨이 갈린다.
"""

CALLUP_POPULARITY_RETENTION = {
    CallUpReason.EARNED: 0.42,
    CallUpReason.EMERGENCY: 0.63,
}
"""콜업 때 남는 인기도 비율.

**NXT의 스타덤은 절반쯤만 따라온다.** 그대로 가져오면 콜업 즉시 월드 임계값 근처에 서서
메인 로스터 커리어가 통째로 사라진다. 큰 물에서는 다시 증명해야 한다.

0.5에서 **0.42로 내렸다.** 문턱을 48 고정에서 76~30 곡선으로 바꾸자 콜업 시점 인기도가
51→63으로 올랐고, 절반을 남기면 메인 로스터 출발점이 25→32가 되어 **그랜드슬램이
57%에서 67%로 튀었다**(250판). 앞선 균형 작업이 일부러 내려놓은 수치라 되돌렸다 —
바뀐 것은 NXT 구간의 길이지 메인 로스터의 난도가 아니어야 한다.

**깜짝 콜업은 덜 깎인다(1.5배).** 대타 출전 자체가 생중계에서 이름을 알리는 사건이라
무대가 스포트라이트를 대신 켜 준다. 그래도 문턱을 넘기 전에 올라가는 것이라 절대
인기도는 정상 콜업보다 낮게 시작한다 — 비율이 높을 뿐 밑천이 적다.
"""


EMERGENCY_CALLUP_FLAG = "callup_emergency"
"""덱과 주차 시뮬을 잇는 플래그. 이 이름의 선택지를 고르면 다음 활동 주차에 올라간다.

카드가 브랜드를 직접 바꾸지 않는 이유: 선택지의 효과는 스탯·컨디션·열기뿐이고, 여기에
브랜드를 더하면 덱 데이터가 소속 규칙을 아는 셈이 된다. 플래그 하나만 넘기고 판정은
규칙이 한다 — 콘텐츠 추가에 코드 리뷰가 필요 없다는 §3-D19의 전제가 유지된다.
"""


def nxt_callup_threshold(week: int) -> int:
    """재적 주차에 따라 내려가는 콜업 문턱 (`EARLY` → `LATE`, 선형)."""
    span = NXT_PATIENCE_WEEKS - NXT_MIN_WEEKS
    elapsed = min(max(week - NXT_MIN_WEEKS, 0), span)
    drop = (NXT_CALLUP_POPULARITY_EARLY - NXT_CALLUP_POPULARITY_LATE) * (elapsed / span)
    return round(NXT_CALLUP_POPULARITY_EARLY - drop)


def should_call_up(run: CareerRun) -> bool:
    """그 주차의 문턱을 넘었거나 NXT 벨트를 모두 감았으면 콜업 (스펙).

    벨트 석권도 하한을 앞당기지는 못한다. 규칙이 둘로 갈리면 "1.5년 전에는 안 올라간다"를
    말할 수 없게 되고, 실제로 그 안에 3벨트를 다 감는 커리어도 없다.
    """
    if run.brand is not Brand.NXT or run.week < NXT_MIN_WEEKS:
        return False
    if run.stats.popularity >= nxt_callup_threshold(run.week):
        return True
    return nxt_titles(run.identity.gender) <= set(run.titles_won)


def call_up(
    run: CareerRun, roll: SeededRoll, reason: CallUpReason = CallUpReason.EARNED
) -> CareerRun:
    """메인 로스터로 올린다. NXT 벨트는 반납하고 인기도는 경로만큼만 남는다."""
    brand = roll.pick((Brand.RAW, Brand.SMACKDOWN))
    kept = round(run.stats.popularity * CALLUP_POPULARITY_RETENTION[reason])
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
