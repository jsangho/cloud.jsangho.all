"""시즌 목표. **진행률은 세계에서 계산하고, 보상은 한 번만 준다.**

## 저장하지 않는다

목표 진행은 `WorldState` 가 이미 가진 사실(로그의 경기 결과 · 인기도 · 타이틀)에서
매번 다시 센다. 진행 칸을 따로 저장하면 그 칸과 로그가 어긋날 수 있고, 세이브
판본도 올려야 한다. 계산만 하면 둘 다 생기지 않는다 — 기존 세이브도 그대로 읽힌다.

## 보상의 중복 방지는 `applied` 하나다

달성한 목표의 보상은 `goal_key(season, code)` 를 `applied` 에 넣으면서 준다.
주차 진행·결산과 같은 장치라서 재시도·동시 요청에 따로 대비할 것이 없다.

## 보상은 주차를 닫을 때 준다

`career_engine._close_week` 가 부른다. 그래서 행동(프로모 등)으로 목표에 닿으면
화면은 그 자리에서 `done` 을 보이지만 보상은 **다음 주차 진행에서** 들어간다 —
`rewarded` 칸이 그 차이를 그대로 내보낸다.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from kayfabe.domain.services.career_world import Balance, LogEntry, WorldState


@dataclass(frozen=True)
class GoalSpec:
    code: str
    label: str
    target: int
    #: 달성 보상 — 인기도 가산. 상한은 `Balance.max_popularity`.
    reward_popularity: int


#: 시즌마다 같은 셋이다. 순서가 화면 순서다.
SEASON_GOALS: tuple[GoalSpec, ...] = (
    GoalSpec(code="season_wins", label="시즌 10승", target=10, reward_popularity=3),
    GoalSpec(code="popularity", label="인기도 50 이상", target=50, reward_popularity=3),
    GoalSpec(code="title", label="챔피언 타이틀 획득", target=1, reward_popularity=5),
)


@dataclass(frozen=True)
class GoalProgress:
    code: str
    label: str
    target: int
    current: int
    done: bool
    #: 보상이 이미 들어갔나. `done` 인데 `False` 면 다음 주차 진행에서 들어간다.
    rewarded: bool
    reward_popularity: int


def goal_key(*, season: int, code: str) -> str:
    return f"goal:s{season}:{code}"


def _season_wins(state: WorldState) -> int:
    return sum(
        1
        for e in state.log
        if e.season == state.season
        and e.kind == "match"
        and e.subject == state.player
        and e.result == "win"
    )


def _title_progress(state: WorldState) -> int:
    """이번 시즌에 타이틀을 땄거나 **지금 들고 있으면** 1.

    지난 시즌에 딴 벨트를 지키고 있는 챔피언에게 "획득 0" 을 보이면 목표가
    벨트를 내려놓으라고 말하는 셈이 된다.
    """
    if state.title_held_by(state.player):
        return 1
    won = any(
        e.season == state.season and e.kind == "title_won" and e.subject == state.player
        for e in state.log
    )
    return 1 if won else 0


def _current(state: WorldState, code: str) -> int:
    if code == "season_wins":
        return _season_wins(state)
    if code == "popularity":
        return state.hero.popularity
    if code == "title":
        return _title_progress(state)
    raise ValueError(f"모르는 목표: {code}")


def evaluate(state: WorldState) -> tuple[GoalProgress, ...]:
    """이번 시즌 목표의 진행. 읽기 전용이다."""
    out = []
    for spec in SEASON_GOALS:
        current = _current(state, spec.code)
        out.append(
            GoalProgress(
                code=spec.code,
                label=spec.label,
                target=spec.target,
                current=current,
                done=current >= spec.target,
                rewarded=goal_key(season=state.season, code=spec.code) in state.applied,
                reward_popularity=spec.reward_popularity,
            )
        )
    return tuple(out)


def award(state: WorldState, *, balance: Balance) -> WorldState:
    """달성했고 아직 보상받지 않은 목표에 보상을 준다. **멱등이다.**

    은퇴한 선수에게는 주지 않는다 — 은퇴 확정 뒤의 인기도 변화는 기록을 흐린다.
    """
    if state.hero.retired:
        return state
    for goal in evaluate(state):
        if not goal.done or goal.rewarded:
            continue
        me = state.hero
        gained = min(balance.max_popularity, me.popularity + goal.reward_popularity)
        roster = tuple(
            replace(w, popularity=gained) if w.name == me.name else w
            for w in state.roster
        )
        state = replace(
            state,
            roster=roster,
            applied=state.applied | {goal_key(season=state.season, code=goal.code)},
            log=state.log
            + (
                LogEntry(
                    season=state.season,
                    week=state.week,
                    kind="goal",
                    subject=me.name,
                    summary=f"시즌 목표 달성 — {goal.label} · 인기도 +{gained - me.popularity}",
                ),
            ),
        )
    return state
