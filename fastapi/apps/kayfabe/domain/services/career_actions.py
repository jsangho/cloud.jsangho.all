"""주간 행동. **포인트를 쓰고, 효과는 여기 한 곳에서만 정한다.**

사용자 요구 §P0 주간 행동 — "행동 효과는 한 곳에서 관리하고, 프론트엔드가 능력치를
임의로 변경하지 않도록 한다." 그래서 프론트가 보내는 것은 **행동 코드와 인수**뿐이고
수치는 서버가 정한다.

## 포인트가 중복 소비를 막는다

행동은 `WorldState.action_points` 를 깎는다. 0이면 거부한다(`ValueError`). 그래서
그 주에 적용되는 행동은 **포인트 수를 넘지 못한다** — §P0 의 "이미 소비한 행동을
중복 적용하지 않도록 한다" 를 막는 것은 이 상한이다.

**멱등 키는 그 상한을 거들 뿐 요청 재시도를 막지 못한다.** 키의 순번이 남은
포인트에서 나오므로(`slot = 최대 - 남음`), 같은 요청이 두 번 들어오면 두 번째는
**다음 순번**을 쓴다 — 실측으로 프로모 두 번이 인기도를 두 번 올린다. 서버에서
"재시도" 와 "이번 주 두 번째 행동" 은 구별되지 않기 때문이고, 구별하려면 요청에
클라이언트가 만든 키가 실려야 한다(지금은 없다). 키가 실제로 막는 것은 **같은
세이브를 두 번 적용하는 경우**다(저장이 실패해 같은 상태로 다시 들어온 경로).

`휴식` 이 돌아온 이유: `career_run` 은 휴식을 "득이 없는 함정" 이라고 빼 뒀다.
그 판단은 그 판본에서 옳았다 — 컨디션도 부상 등급도 없었으니 쉬면 인기도만 깎였다.
이번에는 컨디션·회복력·은퇴 위험이 있어서 **쉬는 것에 값이 있다.**
"""

from __future__ import annotations

from dataclasses import replace

from kayfabe.domain.services import career_relations as relations
from kayfabe.domain.services.career_injury import rest as rest_up
from kayfabe.domain.services.career_world import (
    Ability,
    Balance,
    LogEntry,
    RelationKind,
    WorldState,
)

#: 훈련할 수 있는 능력치. 프론트가 보내는 값은 이 넷 중 하나여야 한다.
TRAINABLE = ("in_ring", "mic", "stamina", "resilience")

#: 행동 종류.
ACTIONS = ("훈련", "프로모", "휴식", "관계", "협상")


def action_key(*, season: int, week: int, slot: int) -> str:
    """행동 한 번의 멱등 키. `slot` 은 그 주의 몇 번째 행동인가."""
    return f"action:s{season}w{week}:{slot}"


def _put(state: WorldState, wrestler) -> WorldState:
    return replace(
        state,
        roster=tuple(w if w.name != wrestler.name else wrestler for w in state.roster),
    )


def _log(
    state: WorldState, *, kind: str, summary: str, other: str | None = None
) -> WorldState:
    return replace(
        state,
        log=state.log
        + (
            LogEntry(
                season=state.season,
                week=state.week,
                kind=kind,
                subject=state.player,
                other=other,
                summary=summary,
            ),
        ),
    )


def perform(
    state: WorldState,
    *,
    action: str,
    balance: Balance,
    target: str | None = None,
) -> WorldState:
    """행동 하나를 적용한다. 포인트가 없거나 입력이 틀리면 `ValueError`.

    **검증을 먼저 전부 한다.** 포인트를 깎은 뒤 인수가 틀린 걸 발견하면 포인트만
    사라진다 — 순서가 그 자체로 규칙이다.
    """
    if action not in ACTIONS:
        raise ValueError(f"action 은 {ACTIONS} 중 하나")
    if state.action_points <= 0:
        raise ValueError("이번 주 행동 포인트를 모두 썼습니다")

    me = state.hero
    if me.retired:
        raise ValueError("은퇴한 선수는 행동할 수 없습니다")

    slot = balance.action_points - state.action_points
    key = action_key(season=state.season, week=state.week, slot=slot)
    if key in state.applied:
        # 같은 요청의 재시도다. 포인트도 효과도 움직이지 않는다.
        return state

    if action == "훈련":
        stat = target or "in_ring"
        if stat not in TRAINABLE:
            raise ValueError(f"훈련 대상은 {TRAINABLE} 중 하나")
        state = _train(state, me, stat)
    elif action == "프로모":
        state = _promo(state, me, balance)
    elif action == "휴식":
        state = _rest(state, me)
    elif action == "관계":
        state = _relate(state, me, target)
    else:
        state = _negotiate(state, me, balance)

    return replace(
        state,
        action_points=state.action_points - 1,
        applied=state.applied | {key},
    )


def _train(state: WorldState, me, stat: str) -> WorldState:
    """훈련 — 지정 능력치 향상. **컨디션을 깎는다.**

    깎지 않으면 훈련이 공짜가 되고, 주당 포인트 전부를 훈련에 넣는 것이 늘 최선이
    된다. 선택지가 하나로 수렴하면 선택지가 아니다.
    """
    gain = 3 if me.condition >= 50 else 1
    ability: Ability = replace(
        me.ability, **{stat: getattr(me.ability, stat) + gain}
    ).clamped()
    trained = replace(me, ability=ability, condition=max(10, me.condition - 8))
    state = _put(state, trained)
    return _log(state, kind="action", summary=f"훈련 — {stat} +{gain}")


def _promo(state: WorldState, me, balance: Balance) -> WorldState:
    """프로모 — 인기도. **마이크 실력이 폭을 정한다.**"""
    gain = 2 + me.ability.mic // 25
    promoted = replace(
        me,
        popularity=min(balance.max_popularity, me.popularity + gain),
        condition=max(10, me.condition - 3),
    )
    state = _put(state, promoted)
    return _log(state, kind="action", summary=f"프로모 — 인기도 +{gain}")


def _rest(state: WorldState, me) -> WorldState:
    """휴식 — 컨디션 회복. 결장 중이면 회복도 돕는다."""
    rested = rest_up(me)
    if me.out_weeks > 1:
        rested = replace(rested, out_weeks=me.out_weeks - 1)
    state = _put(state, rested)
    return _log(state, kind="action", summary=f"휴식 — 컨디션 {rested.condition}")


def _relate(state: WorldState, me, target: str | None) -> WorldState:
    """관계 형성. **대상이 없으면 거부한다** — 조용히 아무 데나 붙이지 않는다."""
    if not target:
        raise ValueError("관계 형성에는 대상 선수가 필요합니다")
    other = state.find(target)
    if other is None:
        raise ValueError(f"로스터에 없는 선수: {target}")
    if other.retired:
        raise ValueError("은퇴한 선수와는 관계를 만들 수 없습니다")
    if other.name == me.name:
        raise ValueError("자기 자신과는 관계를 만들 수 없습니다")

    existing = relations.find(state, me.name, target)
    kind = existing.kind if existing else RelationKind.ALLY
    if kind == RelationKind.RIVAL:
        # 라이벌에게 다가가면 앙금이 식는다 — 관계를 바꾸는 유일한 손길이다.
        state = relations.upsert(
            state, a=me.name, b=target, kind=kind, heat_delta=-15, week=state.week
        )
        summary = f"관계 — {target}와의 앙금을 식혔다"
    else:
        state = relations.upsert(
            state, a=me.name, b=target, kind=kind, heat_delta=18, week=state.week
        )
        state = relations.upsert(
            state, a=target, b=me.name, kind=kind, heat_delta=12, week=state.week
        )
        summary = f"관계 — {target}와 가까워졌다"
    return _log(state, kind="action", summary=summary, other=target)


def _negotiate(state: WorldState, me, balance: Balance) -> WorldState:
    """협상 — **조건이 맞을 때만 기회가 생긴다**(§P0 — "조건 충족 시").

    자격이 없으면 아무 기회도 만들지 않고 그 사실을 로그에 적는다. 조용히 성공한
    것처럼 보이면 화면이 거짓을 말한다.
    """
    open_belts = [
        t
        for t in state.titles
        if t.brand == me.brand and me.popularity >= t.required_popularity
    ]
    if not open_belts:
        return _log(
            state,
            kind="action",
            summary=f"협상 — 자격 미달 (인기도 {me.popularity})",
        )
    belt = max(open_belts, key=lambda t: t.required_popularity)
    state = replace(
        state, applied=state.applied | {f"shot:s{state.season}w{state.week + 1}"}
    )
    return _log(state, kind="action", summary=f"협상 — {belt.name} 도전권을 얻었다")


def reset_points(state: WorldState, balance: Balance) -> WorldState:
    """새 주의 포인트를 채운다. 주차 진행이 부른다."""
    return replace(state, action_points=balance.action_points)
