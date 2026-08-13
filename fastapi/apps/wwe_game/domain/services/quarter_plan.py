"""분기 목표가 규칙에 곱해지는 자리 (하네스 §3-D80).

**한 곳에 모은다.** 배수를 쓰는 함수가 예닐곱이라 각자 `GOALS[run.goal]`을 뒤지면,
"목표가 없을 때"(옛 세이브·체험판·아직 안 고름)의 처리가 일곱 군데로 갈린다.
"""

from __future__ import annotations

from wwe_game.domain.entities.career_run import CareerRun
from wwe_game.domain.exceptions import (
    CannotAffordGoalError,
    NoGoalNeededError,
)
from wwe_game.domain.value_objects.quarter_goal import (
    GOALS,
    QUARTER_WEEKS,
    GoalSpec,
    QuarterGoal,
    affordable,
    quarter_of,
    spec_of,
)
from wwe_game.domain.value_objects.title import Brand


def plan_of(run: CareerRun) -> GoalSpec:
    """지금 걸려 있는 목표. **분기가 지났으면 안 걸려 있다.**

    지난 분기의 목표가 이번 분기까지 효력을 갖지 않게 하는 것이 이 함수의 일이다 —
    `goal`만 보면 목표를 한 번 고르고 30년을 그 배수로 산다.
    """
    if run.goal is None or run.goal_quarter != quarter_of(run.week):
        return spec_of(None)
    return spec_of(run.goal)


def needs_goal(run: CareerRun) -> bool:
    """지금 목표를 물어야 하는가 (§3-D80).

    **NXT에서는 묻지 않는다** (2026-08-13 사용자 결정). 육성 브랜드는 남이 짜 주는
    구간이다 — 무엇을 걸지 정하는 것은 메인 로스터의 일이고, **콜업이 그 시작점**이다
    (§3-D22). 커리어의 장이 바뀌는 사건에 "이제부터 내가 정한다"가 붙는다.

    데뷔 직후에도 안 묻는 이유가 같다: 아무것도 모르는 채 고르라고 하면 그건 선택이
    아니라 제비뽑기다.

    **무소속에도 묻지 않는다** (§3-D50). 인디를 도는 구간은 단체가 짜 주는 그림이
    없어서 "벨트를 노린다"가 성립하지 않는다 — 그 구간의 목표는 하나뿐이고
    (돌아가는 것) 그건 규칙이 이미 처리한다.
    """
    return (
        run.is_active
        and run.is_signed
        and run.brand is not Brand.NXT
        and run.week < QUARTER_WEEKS * 120
        and run.goal_quarter != quarter_of(run.week)
    )


def growth_factor(run: CareerRun, stat: str) -> float:
    """그 스탯의 성장 배수. 목표가 안 건드리는 스탯은 1.0이다."""
    return (plan_of(run).growth or {}).get(stat, 1.0)


def choose(run: CareerRun, goal: QuarterGoal) -> CareerRun:
    """이번 분기에 걸 것을 정한다 (§3-D80). **비용은 여기서 나간다.**

    잔액이 모자라는 목표는 `affordable`이 목록에서 빼므로 화면에는 안 뜨지만,
    체험판은 상태를 손댈 수 있어(§3-D8) 여기서도 막는다 — 신뢰하지 않되 규칙에
    맞으면 그대로 받는다.
    """
    if not needs_goal(run):
        raise NoGoalNeededError("지금은 목표를 고를 때가 아닙니다.")
    spec = GOALS[goal]
    if spec.cost > run.money:
        raise CannotAffordGoalError("잔액이 모자랍니다.")
    return run.evolve(
        goal=goal,
        goal_quarter=quarter_of(run.week),
        money=run.money - spec.cost,
    )


def options(run: CareerRun) -> tuple[GoalSpec, ...]:
    """지금 고를 수 있는 목표들. 잔액이 목록을 깎는다 (§3-D48)."""
    return affordable(run.money)


def drift(run: CareerRun) -> CareerRun:
    """묻는 자리를 지나쳤다 — **그냥 뛴 것으로 넘긴다** (§3-D80).

    §11-1(*'다음'만 눌러도 끝까지 간다*)을 지키는 자리다. 배수가 전부 1.0이고
    비용도 없으므로, 목표를 한 번도 안 고른 커리어는 지금까지와 똑같이 흐른다.
    """
    return run.evolve(goal=QuarterGoal.DRIFT, goal_quarter=quarter_of(run.week))
