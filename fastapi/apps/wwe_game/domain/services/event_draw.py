"""이벤트 추첨과 선택 판정 (하네스 §5, 덱 스키마 §1-2).

세 가지를 한다.

1. **조건 통과** — `requires`를 세이브 상태와 대조한다
2. **추첨** — 예산 기반 확률 + 쿨다운 + 가중치. 전부 시드 파생이다
3. **판정** — 고른 선택지의 효과를 세이브에 반영한다

**억지로 띄우지 않는다.** 조건을 통과한 카드가 없으면 이벤트 없이 그 주차를 넘긴다.
"""

from __future__ import annotations

from wwe_game.domain.constants import career_rules as rules
from wwe_game.domain.constants.career_clock import CAREER_WEEKS
from wwe_game.domain.constants.event_deck import BY_CODE, DECK, Choice, EventCard
from wwe_game.domain.entities.career_run import CareerRun, EventInstance
from wwe_game.domain.exceptions import InvalidChoiceError
from wwe_game.domain.services import rivalry_engine, seeded_roll
from wwe_game.domain.services.seeded_roll import SeededRoll
from wwe_game.domain.value_objects.game_mode import GAME_MODES

COOLDOWN_MIN = 8
COOLDOWN_DIVISOR = 2
COOLDOWN_RELAX_ATTEMPTS = 2
"""쿨다운 = `max(8, 남은_후보수 // 2)`. 후보가 마르면 절반씩 완화해 최대 2회 재시도한다.

완화가 없으면 조건이 겹친 상태(부상 중 + 특정 액트)에서 후보가 서너 장뿐일 때
이벤트가 영영 안 뜬다.

**나눗수를 3에서 2로 낮췄다**(2026-08-07). 3일 때는 후보 148장 기준 쿨다운이 49회라
30년짜리 `weekly` 한 판에서 **같은 카드가 최대 7회** 나와 §11-19(5회 이하)를 넘고
있었다. 2로 올리면 74회가 되고 같은 조건에서 5회로 내려간다.
"""

RECENT_MEMORY = 512
"""들고 있는 최근 이벤트 코드 수. **커리어 전체를 덮는다.**

두 가지에 쓰인다.

1. **쿨다운** — 최근 N회에 나온 카드는 후보에서 뺀다
2. **본문 변주 순환** — 그 카드가 지금까지 몇 번 나왔는지 세어 다음 변주를 고른다

2번 때문에 짧으면 안 된다. 128일 때는 쿨다운(74회)이 기억의 절반을 넘어 **한 카드의
이전 등장이 최대 한 번만 남았고**, 그래서 변주가 0번과 1번 사이만 오갔다 — 2번 변주는
거의 쓰이지 않고 같은 문장이 한 판에 5회까지 나왔다(§11-6 기준 3회).

가장 큰 예산(320)보다 넉넉해야 카운트가 정확하다. 아래 임포트 검증이 그걸 지킨다.
저장 비용은 코드 문자열 수백 개로, 세이브 하나에 10KB 남짓이다.
"""


def _stat_of(run: CareerRun, name: str) -> int:
    if name == "wear":
        return run.condition.wear
    return int(getattr(run.stats, name))


def is_eligible(run: CareerRun, card: EventCard) -> bool:
    """조건을 하나라도 어기면 후보에서 빠진다."""
    r = card.requires
    if card.once and card.code in run.seen_events:
        return False
    if r.acts and run.act not in r.acts:
        return False
    if r.brands and run.brand not in r.brands:
        return False
    if run.week < r.min_week:
        return False
    if r.max_week is not None and run.week > r.max_week:
        return False
    if r.min_age is not None and run.age < r.min_age:
        return False
    if r.max_age is not None and run.age > r.max_age:
        return False
    for name, low, high in r.stats:
        if not low <= _stat_of(run, name) <= high:
            return False
    if r.alignment is not None and not (
        r.alignment[0] <= run.stats.alignment <= r.alignment[1]
    ):
        return False
    if r.regions and run.identity.region not in r.regions:
        return False
    if r.style_families and run.identity.style_family not in r.style_families:
        return False
    if r.play_styles and run.identity.play_style not in r.play_styles:
        return False
    if run.condition.is_injured:
        # **다친 동안에는 등급을 명시한 카드만 뜬다** (§3-D37).
        #
        # 다른 조건은 "생략 = 무관"이지만 여기만 반대다. 무관으로 두었더니 결장 중인
        # 선수에게 `ring_kickout_at_one`(원 카운트에 킥아웃)·`ring_apron_spot`이
        # 떴다 — 링에 못 서는 사람이 링에서 겪는 사건이다. 부상 주차의 21%가 그랬다.
        #
        # 남는 것은 `events_condition.json`의 재활·복귀 카드들이고, 전부 백스테이지다.
        if run.condition.grade not in r.condition_grades:
            return False
    elif r.condition_grades and run.condition.grade not in r.condition_grades:
        return False
    if not r.flags <= run.flags:
        return False
    if r.holds_briefcase and not run.briefcase:
        return False
    if r.rivalry_stages:
        stages = {rv.stage for rv in run.rivalries}
        if not (r.rivalry_stages & stages):
            return False
    return True


def candidates(run: CareerRun) -> tuple[EventCard, ...]:
    return tuple(c for c in DECK if is_eligible(run, c))


def event_chance(run: CareerRun) -> float:
    """이번 주차에 이벤트가 뜰 확률 = 남은 예산 / 남은 주차.

    **매 주차 다시 계산한다.** 고정 확률로 두면 초반에 예산을 몰아 쓰고 후반이 조용해진다.
    """
    weeks_left = max(1, CAREER_WEEKS - run.week)
    budget_left = max(0, run.mode.event_budget - run.events_fired)
    chance = min(1.0, budget_left / weeks_left)
    if run.condition.is_injured:
        # 다친 동안에는 드물게 (§3-D37). 여기서 덜 쓴 예산은 복귀 뒤에 돌아온다.
        chance *= rules.INJURY_EVENT_FACTOR
    return chance


def _cooldown(pool_size: int) -> int:
    return max(COOLDOWN_MIN, pool_size // COOLDOWN_DIVISOR)


def _weighted(pool: tuple[EventCard, ...], roll: SeededRoll) -> EventCard:
    total = sum(c.weight for c in pool)
    pick = roll.between(1, total)
    cursor = 0
    for card in pool:
        cursor += card.weight
        if pick <= cursor:
            return card
    return pool[-1]  # pragma: no cover - 가중치 합 불일치


def draw_event(run: CareerRun) -> EventInstance | None:
    """이번 주차의 이벤트. 없으면 None.

    쿨다운은 후보 목록을 줄일 뿐이라 **시드 결정성이 깨지지 않는다.**
    """
    roll = SeededRoll(run.seed, run.week, seeded_roll.EVENT)
    if not roll.chance(event_chance(run)):
        return None

    pool = candidates(run)
    if not pool:
        return None

    cooldown = _cooldown(len(pool))
    for _ in range(COOLDOWN_RELAX_ATTEMPTS + 1):
        recent = set(run.recent_events[-cooldown:]) if cooldown else set()
        fresh = tuple(c for c in pool if c.code not in recent)
        if fresh:
            pool = fresh
            break
        cooldown //= 2
    else:  # pragma: no cover - 완화해도 비면 억지로 띄우지 않는다
        return None

    card = _weighted(pool, roll)
    rival = rivalry_engine.top_rivalry(run)
    return EventInstance(
        code=card.code,
        week=run.week,
        body_index=_body_index(run, card),
        rival_name=rival.rival_name if rival else None,
    )


def _body_index(run: CareerRun, card: EventCard) -> int:
    """다음에 보여줄 본문 변주. **굴리지 않고 돌린다.**

    독립적으로 굴리면 같은 카드가 다섯 번 뜰 때 어느 변주가 겹칠 확률이 그대로 남는다 —
    실측에서 같은 문장이 한 판에 5회까지 나왔다(§11-6 기준 3회). 지금까지 몇 번 나왔는지를
    세어 차례로 돌리면 세 변주를 고르게 쓰고, 다섯 번 등장해도 최다 2회다.

    시드를 더하는 이유: 안 그러면 **모든 커리어가 같은 변주로 시작한다.** 판마다 출발점이
    달라야 첫 등장부터 같은 장면이 반복되지 않는다.
    """
    seen = run.recent_events.count(card.code)
    return (run.seed + seen) % len(card.bodies)


def resolve_choice(run: CareerRun, choice_code: str) -> CareerRun:
    """대기 중 이벤트에 답한다. 스탯·컨디션·플래그·대립 열기를 한 번에 반영한다."""
    pending = run.pending_event
    if pending is None:
        raise ValueError("대기 중인 이벤트가 없습니다.")
    card = BY_CODE[pending.code]
    choice = card.choice(choice_code)
    if choice is None:
        raise InvalidChoiceError(f"선택할 수 없는 항목입니다: {choice_code}")
    return _apply(run, card, choice)


def _apply(run: CareerRun, card: EventCard, choice: Choice) -> CareerRun:
    from wwe_game.domain.value_objects.condition import InjuryGrade

    roll = SeededRoll(run.seed, run.week, f"{seeded_roll.EVENT}:{choice.code}")

    condition = run.condition.with_wear(choice.wear_delta)
    if choice.career_ending:
        # **도박이지 자살이 아니다.** 확정 종료로 두었더니 그 카드를 만난 커리어의
        # 대부분이 거기서 끝났다 — 한 장이 결과를 통째로 정하는 셈이었다.
        # 굴림에 걸렸을 때만 커리어가 닫힌다.
        if roll.chance(choice.injury_risk):
            condition = condition.injured(InjuryGrade.CAREER_ENDING, 1)
        else:
            condition = condition.injured(InjuryGrade.SERIOUS, roll.between(14, 30))
    elif choice.injury_risk > 0 and roll.chance(choice.injury_risk):
        grade = (
            InjuryGrade.SERIOUS
            if roll.chance(rules.INJURY_GRADE_WEIGHTS[1][1] / 100)
            else InjuryGrade.MINOR
        )
        low, high = (10, 30) if grade is InjuryGrade.SERIOUS else (2, 6)
        condition = condition.injured(grade, roll.between(low, high))

    rivalries = run.rivalries
    if choice.heat and rivalries:
        hottest = rivalry_engine.top_rivalry(run)
        rivalries = tuple(
            rivalry_engine.with_heat(r, choice.heat)
            if hottest is not None and r.rival_name == hottest.rival_name
            else r
            for r in rivalries
        )

    seen = run.seen_events | {card.code} if card.once else run.seen_events
    recent = (*run.recent_events, card.code)[-RECENT_MEMORY:]

    return run.evolve(
        stats=run.stats.apply_event(choice.stat_deltas()),
        condition=condition,
        rivalries=rivalries,
        flags=run.flags | choice.flags,
        seen_events=seen,
        recent_events=recent,
        events_fired=run.events_fired + 1,
        pending_event=None,
    )


# 기억이 가장 큰 예산보다 짧으면 변주 순환이 조용히 어긋난다 (위 `RECENT_MEMORY` 참조).
_max_budget = max(_mode.event_budget for _mode in GAME_MODES.values())
if RECENT_MEMORY <= _max_budget:  # pragma: no cover - 임포트 시 구조 검증
    raise RuntimeError(
        f"RECENT_MEMORY({RECENT_MEMORY})가 최대 이벤트 예산({_max_budget})보다 작습니다"
    )
