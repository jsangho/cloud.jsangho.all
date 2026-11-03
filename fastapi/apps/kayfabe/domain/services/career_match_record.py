"""경기 기록. **이미 계산된 값을 옮겨 적을 뿐이다 — 뽑지도, 다시 계산하지도 않는다.**

`career_engine.advance_week` 가 경기 하나를 처리하는 동안 두 번 사진을 찍는다.

    1. 시뮬레이션이 끝났고 `_apply_outcome` 이 아직 돌지 않은 때 → `snapshot`
    2. `_apply_outcome` 과 `maybe_injure` 가 끝났고 주차 마감 전 → `snapshot`

그 둘과 `MatchOutcome` · `Card` · `WeekReport` 를 `build` 가 `MatchRecord` 한 장으로
묶고, `append` 가 세계에 붙인다. **이 파일에는 `career_rng` import 가 없다** —
기록이 생겨도 승부·평점·피니시가 바뀌지 않는다는 것이 이 한 줄로 보장된다.

## 왜 경기 시점에 찍어야 하나

세계에는 **현재 값만** 있다. 지난 경기의 인기도·컨디션은 어디에도 남지 않고,
시드로 다시 돌려도 그 주의 능력치가 없으니 재현되지 않는다. 그 순간을 놓치면
영영 복원할 수 없다 — 그래서 화면(전후 비교)보다 저장이 먼저다.

## 기록은 불변이다

`append` 말고는 `matches` 를 건드리는 함수가 없다. 같은 id 가 이미 있으면 붙이지
않는다(재시도 방어). 상한을 넘으면 **가장 오래된 것부터** 버리고, 남은 것의 내용은
바꾸지 않는다.
"""

from __future__ import annotations

from dataclasses import replace

from kayfabe.domain.services.career_match import MatchOutcome, power_parts
from kayfabe.domain.services.career_world import (
    STATE_FIELDS,
    HeatChange,
    Injury,
    MatchRecord,
    ParticipantRecord,
    WorldState,
    Wrestler,
)

#: 보존하는 플레이어 경기 수 — 두 시즌(52주 × 2). 사용자 결정(Phase 0 #6).
MAX_MATCH_RECORDS = 104

#: 핀을 딴 선수와 당한 선수가 **있는** 피니시. 나머지에는 그 역할이 없다.
PINFALL = "핀폴"


def match_id(*, season: int, week: int) -> str:
    """플레이어 경기의 id. **플레이어는 한 주에 한 경기**라서 시즌·주차로 정해진다.

    로그의 `match` 줄(시즌·주차)에서 이 id 를 다시 만들 수 있으므로 로그에 칸을
    더하지 않는다. 접미사 `:p` 는 플레이어 경기라는 뜻이다 — NPC 경기가 생기면
    다른 접미사를 쓴다.
    """
    return f"s{season}w{week}:p"


def state_of(w: Wrestler) -> tuple[int, ...]:
    """`STATE_FIELDS` 순서의 값. 순서는 그 상수 하나가 정한다."""
    return tuple(int(getattr(w, field)) for field in STATE_FIELDS)


def snapshot(state: WorldState, names: tuple[str, ...]) -> dict[str, tuple[int, ...]]:
    """참가자들의 지금 상태."""
    return {name: state_of(state.require(name)) for name in names}


def heat_between(
    state: WorldState, names: tuple[str, ...]
) -> dict[tuple[str, str], int]:
    """참가자끼리의 방향 있는 관계 heat. 관계가 없는 쌍은 빠진다."""
    inside = set(names)
    return {
        (r.a, r.b): r.heat
        for r in state.relationships
        if r.a in inside and r.b in inside and r.a != r.b
    }


def build(
    *,
    season: int,
    week: int,
    brand: str,
    reason: str,
    title: str | None,
    title_changed: bool,
    outcome: MatchOutcome,
    before_state: WorldState,
    before: dict[str, tuple[int, ...]],
    after: dict[str, tuple[int, ...]],
    heat_before: dict[tuple[str, str], int],
    heat_after: dict[tuple[str, str], int],
    injury: Injury | None,
    popularity_delta: int,
) -> MatchRecord:
    """경기 기록 한 장. 인수는 전부 엔진이 **이미 계산한** 값이다.

    `teams` 는 `outcome.team_a`(플레이어 쪽) · `team_b` 순서다 — 싱글은
    `simulate_single(a=플레이어, ...)` 가, 태그는 `simulate_tag(team_a=(플레이어, 파트너))`
    가 그렇게 채운다.
    """
    teams = (tuple(outcome.team_a), tuple(outcome.team_b))
    winner_side = 0 if outcome.winner in teams[0] else 1
    pinfall = outcome.finish == PINFALL
    participants = tuple(
        ParticipantRecord(
            name=name,
            side=side,
            power=_power_of(before_state.require(name)),
            before=before[name],
            after=after[name],
        )
        for side, team in enumerate(teams)
        for name in team
    )
    heat = tuple(
        HeatChange(a=a, b=b, before=heat_before.get((a, b)), after=value)
        for (a, b), value in sorted(heat_after.items())
        if heat_before.get((a, b)) != value
    )
    return MatchRecord(
        id=match_id(season=season, week=week),
        season=season,
        week=week,
        brand=brand,
        kind=outcome.kind,
        reason=reason,
        title=title,
        title_changed=title_changed,
        teams=teams,
        winner_side=winner_side,
        probability=outcome.probability,
        finish=outcome.finish,
        rating=outcome.rating,
        finisher=outcome.winner,
        scorer=outcome.winner if pinfall else None,
        pinned=outcome.loser if pinfall else None,
        participants=participants,
        heat=heat,
        injury=injury,
        popularity_delta=popularity_delta,
    )


def _power_of(w: Wrestler) -> tuple[float, float, float]:
    parts = power_parts(w)
    return (parts.skill, parts.draw, parts.body)


def append(state: WorldState, record: MatchRecord) -> WorldState:
    """기록을 붙인다. **같은 id 면 아무것도 하지 않는다.** 상한을 넘으면 오래된 것부터 버린다."""
    if any(m.id == record.id for m in state.matches):
        return state
    return replace(state, matches=(state.matches + (record,))[-MAX_MATCH_RECORDS:])


#: `missing_reason` 의 답.
BEFORE_RECORDS = "before_records"
TRIMMED = "trimmed"
UNEXPLAINED = "unexplained"


def missing_reason(state: WorldState, *, season: int, week: int) -> str | None:
    """그 주차 플레이어 경기의 기록이 **왜 없는가.** 있으면 `None`.

    **경기가 있었던 주차에만 묻는다**(로그의 `match` 줄). 쉬거나 결장한 주차는
    애초에 기록할 경기가 없다 — 이 함수는 그것을 가리지 못한다.

        before_records  `match_records_since` 이전 — 기록 도입 전 경기
        trimmed         남은 가장 오래된 기록보다 이전 — 보존 상한으로 잘렸다
        unexplained     둘 다 아닌데 없다 — 세이브가 자기모순이다
    """
    rid = match_id(season=season, week=week)
    if any(m.id == rid for m in state.matches):
        return None
    since = state.match_records_since
    if since is not None and (season, week) < since:
        return BEFORE_RECORDS
    if state.matches and (season, week) < (
        state.matches[0].season,
        state.matches[0].week,
    ):
        return TRIMMED
    return UNEXPLAINED
