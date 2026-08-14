"""분기 목표 — **먼저 정하는 유일한 자리** (하네스 §3-D80).

지금까지 이 게임의 선택은 전부 반응형이었다: 카드 261장·선택지 559개가 모두
"일이 벌어졌다 → 어떻게 반응할래"이고, 플레이어가 **먼저 무엇을 하겠다고 정하는
자리가 없었다**. 여기가 그 자리다.

## 왜 분기인가

**달력의 단위이지 진행 단위가 아니다.** 13주 고정이라 네 모드가 전부 같은 횟수를
고른다(30년에 120번) — `weeks_per_tick`에 묶으면 주 단위 모드는 1560번을 고르고
연 단위 모드는 30번을 골라, 같은 게임이 아니게 된다.

## 배수만 든다

목표는 **확률을 사지 스탯을 사지 않는다.** §13-Q13과 §3-D41에서 두 번 겪은 사고다 —
값을 직접 얹으면 인기도 경제가 곧장 무너진다. "몸을 만든다"는 마모 회복 배수를
사는 것이지 경기력 +5를 사는 것이 아니다.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final


class QuarterGoal(StrEnum):
    """한 분기에 거는 것. **`DRIFT`가 있어야 한다** — 매번 무언가를 걸어야 하면
    선택이 아니라 세금이 된다."""

    TITLE = "title"
    RIVALRY = "rivalry"
    BODY = "body"
    MIC = "mic"
    MONEY = "money"
    DRIFT = "drift"


@dataclass(frozen=True)
class GoalSpec:
    goal: QuarterGoal
    label: str
    blurb: str
    cost: int
    """그 분기를 시작할 때 나가는 돈. 잔액이 모자라면 **목록에서 빠진다** —
    못 고르는 것이 곧 가난의 의미다 (§3-D48)."""
    title_shot: float = 1.0
    injury: float = 1.0
    heat: float = 1.0
    wear_recovery: float = 1.0
    promo: float = 1.0
    pay: float = 1.0
    growth: dict[str, float] | None = None
    """스탯별 성장 배수. **성장분에 곱한다** — 더하지 않는다."""


_G = QuarterGoal

GOALS: Final[dict[QuarterGoal, GoalSpec]] = {
    _G.TITLE: GoalSpec(
        _G.TITLE,
        "벨트를 노린다",
        "타이틀 그림 안으로 밀고 들어간다. 몸이 더 상한다.",
        cost=12_000,
        title_shot=1.6,
        injury=1.2,
    ),
    _G.RIVALRY: GoalSpec(
        _G.RIVALRY,
        "대립을 키운다",
        "한 사람과의 이야기에 집중한다. 이름이 알려진다.",
        cost=0,
        heat=1.6,
        growth={"popularity": 1.35},
    ),
    _G.BODY: GoalSpec(
        _G.BODY,
        "몸을 만든다",
        "트레이너를 붙인다. 타이틀 그림에서는 잠시 멀어진다.",
        cost=30_000,
        injury=0.65,
        wear_recovery=2.0,
        title_shot=0.6,
    ),
    _G.MIC: GoalSpec(
        _G.MIC,
        "마이크를 간다",
        "프로모 코치를 쓴다. 말이 먹히기 시작한다.",
        cost=9_000,
        promo=1.4,
        growth={"mic_work": 1.5},
    ),
    _G.MONEY: GoalSpec(
        _G.MONEY,
        "돈을 번다",
        "행사와 사인회를 돈다. 링 밖의 일이라 이름값은 덜 오른다.",
        cost=0,
        pay=1.25,
        growth={"popularity": 0.75},
    ),
    _G.DRIFT: GoalSpec(
        _G.DRIFT,
        "그냥 뛴다",
        "특별히 거는 것 없이 시즌을 보낸다.",
        cost=0,
    ),
}

QUARTER_WEEKS: Final = 13
"""한 분기. 30년이면 120번 고른다."""

DEFAULT: Final = GOALS[_G.DRIFT]
"""목표가 없을 때의 배수 — 전부 1.0이다. 옛 세이브와 체험판이 이 자리를 쓴다."""


def spec_of(goal: QuarterGoal | None) -> GoalSpec:
    return DEFAULT if goal is None else GOALS[goal]


def quarter_of(week: int) -> int:
    """그 주차가 몇 번째 분기인가 (0부터). 목표를 다시 물을 때를 여기서 안다."""
    return max(0, week) // QUARTER_WEEKS


def affordable(money: int) -> tuple[GoalSpec, ...]:
    """지금 잔액으로 고를 수 있는 것들. 순서는 선언 순서 그대로다."""
    return tuple(spec for spec in GOALS.values() if spec.cost <= money)
