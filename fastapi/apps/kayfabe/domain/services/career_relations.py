"""관계. **수치만 움직이고 끝나지 않는다** — 임계값이 사건 후보를 만든다.

사용자 요구 §P0 관계 — "관계 수치만 변경하고 끝내지 말고, 일정 조건에서 실제
사건이나 게임 진행상의 효과가 발생하게 한다. 다만 관계 임계값을 넘었다고 모든
이벤트를 강제 발생시키지 말고, 조건을 만족하는 이벤트 후보를 생성해 게임 규칙에
따라 처리한다."

그래서 이 파일은 **후보까지만** 만든다(`candidates`). 실제로 열릴지는
`career_events` 가 정하고, 그쪽이 주당 개수와 중복을 본다. 둘을 합치면 관계가
임계값을 넘는 순간 사건이 쏟아진다.

## 방향이 있다

`Relationship` 은 `a → b` 한 방향이다. 배신이 비대칭이기 때문이다 — 배신한 쪽은
아직 동맹으로 알고, 당한 쪽은 라이벌이 된다. 한 줄로 묶으면 그걸 못 적는다.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from kayfabe.domain.services.career_world import (
    RelationKind,
    Relationship,
    WorldState,
)

#: 라이벌 관계가 "경기로 풀어야 하는" 수준에 닿는 heat.
FEUD_HEAT = 60
#: 동맹이 태그팀으로 굳는 heat.
TEAM_HEAT = 55
#: 동맹이 금 가는 heat — 이 아래로 떨어지면 배신 후보가 된다.
BETRAYAL_HEAT = 15


@dataclass(frozen=True)
class RelationCandidate:
    """관계가 만든 **사건 후보**. 사건이 아니다.

    `career_events` 가 이걸 받아 열지 말지 정한다. 그 한 단계가 "임계값 넘으면
    전부 발생" 을 막는다.
    """

    kind: str
    subject: str
    other: str
    #: 우선순위. 높은 것부터 고려된다.
    weight: float
    reason: str


def is_feud(relation: Relationship) -> bool:
    """**경기로 풀어야 하는 수준의 라이벌 관계인가.**

    `kind == RIVAL` 만으로는 라이벌을 셀 수 없다 — `after_match` 가 경기마다 진 쪽을
    라이벌로 올리므로 한 시즌만 돌면 **상대 거의 전원이** 라이벌 kind 를 갖는다
    (실측: 경기 30건 중 30건). 끓는 관계를 가르는 것은 `FEUD_HEAT` 이고, 그 선이
    여기 한 곳에 있어야 사건 생성과 화면이 같은 기준을 쓴다.
    """
    return relation.kind == RelationKind.RIVAL and relation.heat >= FEUD_HEAT


def find(state: WorldState, a: str, b: str) -> Relationship | None:
    for r in state.relationships:
        if r.a == a and r.b == b:
            return r
    return None


def upsert(
    state: WorldState,
    *,
    a: str,
    b: str,
    kind: str,
    heat_delta: int = 0,
    week: int = 1,
    note: str = "",
) -> WorldState:
    """관계를 만들거나 고친다. **종류가 바뀌면 이력에 남는다.**

    이력을 남기는 것은 §P0 관계의 "상태 변경 이력" 이고, 은퇴 선수 프로필이
    "주요 라이벌" 을 적을 때도 읽는다(§5).
    """
    existing = find(state, a, b)
    if existing is None:
        fresh = Relationship(
            a=a,
            b=b,
            kind=kind,
            heat=max(-100, min(100, heat_delta)),
            started_week=week,
            last_week=week,
            history=((note,) if note else ()),
        )
        return replace(state, relationships=state.relationships + (fresh,))

    history = existing.history
    if kind != existing.kind:
        history = history + (f"{existing.kind}→{kind}",)
    if note:
        history = history + (note,)
    updated = replace(
        existing,
        kind=kind,
        heat=max(-100, min(100, existing.heat + heat_delta)),
        last_week=week,
        history=history,
    )
    return replace(
        state,
        relationships=tuple(
            updated if (r.a == a and r.b == b) else r for r in state.relationships
        ),
    )


def after_match(
    state: WorldState, *, winner: str, loser: str, week: int, title_match: bool
) -> WorldState:
    """경기 뒤 관계 변화. **진 쪽이 라이벌이 된다.**

    양쪽을 각각 쓴다 — 이긴 쪽에게 상대는 "넘은 상대" 이고 진 쪽에게는 "되갚을
    상대" 다. 타이틀전이면 더 끓는다.
    """
    gain = 14 if title_match else 8
    existing = find(state, loser, winner)
    kind = RelationKind.RIVAL
    if existing is not None and existing.kind in (
        RelationKind.ALLY,
        RelationKind.TAG_TEAM,
    ):
        # 동맹끼리 붙었다. 관계가 바로 라이벌로 뒤집히지는 않고 신뢰만 깎인다.
        state = upsert(
            state,
            a=loser,
            b=winner,
            kind=existing.kind,
            heat_delta=-gain,
            week=week,
            note="동맹과 맞붙었다",
        )
        return state

    state = upsert(state, a=loser, b=winner, kind=kind, heat_delta=gain, week=week)
    state = upsert(state, a=winner, b=loser, kind=kind, heat_delta=gain // 2, week=week)
    return state


def candidates(state: WorldState, subject: str) -> tuple[RelationCandidate, ...]:
    """관계가 만든 사건 후보들. **여기서는 아무것도 발생하지 않는다.**

    네 종류를 본다 — 라이벌의 도발 · 동맹 제안 · 태그팀 결성 · 배신.
    """
    found: list[RelationCandidate] = []
    me = state.find(subject)
    if me is None or not me.bookable:
        return ()

    for r in state.relations_of(subject):
        other_name = r.other(subject)
        other = state.find(other_name)
        # **은퇴한 선수는 사건을 만들지 않는다.** 기록은 남지만 세계에 개입하지 않는다.
        if other is None or other.retired:
            continue

        if is_feud(r):
            found.append(
                RelationCandidate(
                    kind="rival_taunt",
                    subject=subject,
                    other=other_name,
                    weight=r.heat / 100.0 + 0.3,
                    reason=f"{other_name}와의 앙금이 {r.heat}까지 올랐다",
                )
            )
        if r.kind == RelationKind.ALLY and r.heat >= TEAM_HEAT:
            found.append(
                RelationCandidate(
                    kind="tag_team_offer",
                    subject=subject,
                    other=other_name,
                    weight=r.heat / 100.0,
                    reason=f"{other_name}와 호흡이 맞는다",
                )
            )
        if (
            r.kind in (RelationKind.ALLY, RelationKind.TAG_TEAM)
            and r.heat <= BETRAYAL_HEAT
        ):
            found.append(
                RelationCandidate(
                    kind="betrayal",
                    subject=subject,
                    other=other_name,
                    weight=0.8 - r.heat / 100.0,
                    reason=f"{other_name}와의 신뢰가 {r.heat}까지 떨어졌다",
                )
            )

    # 아직 아무 관계도 없는 같은 브랜드 선수 — 동맹 제안 후보.
    if len([r for r in state.relations_of(subject) if r.a == subject]) < 3:
        known = {r.other(subject) for r in state.relations_of(subject)}
        strangers = sorted(
            w.name
            for w in state.roster
            if w.name != subject
            and w.name not in known
            and w.brand == me.brand
            and w.bookable
        )
        if strangers:
            found.append(
                RelationCandidate(
                    kind="ally_offer",
                    subject=subject,
                    other=strangers[0],
                    weight=0.35,
                    reason=f"{strangers[0]}가 같은 브랜드에 있다",
                )
            )

    return tuple(sorted(found, key=lambda c: -c.weight))


def betray(state: WorldState, *, traitor: str, victim: str, week: int) -> WorldState:
    """배신. **비대칭으로 쓴다** — 그래서 관계가 방향을 갖는 것이다.

    당한 쪽은 라이벌이 되고 heat 가 뛴다. 배신한 쪽은 관계를 끊는다(`history` 에
    남으므로 조회는 된다).
    """
    state = upsert(
        state,
        a=victim,
        b=traitor,
        kind=RelationKind.RIVAL,
        heat_delta=70,
        week=week,
        note="배신당했다",
    )
    state = upsert(
        state,
        a=traitor,
        b=victim,
        kind=RelationKind.RIVAL,
        heat_delta=20,
        week=week,
        note="배신했다",
    )
    return state


def tag_partner(state: WorldState, subject: str) -> str | None:
    """지금의 태그 파트너. 둘 이상이면 heat 가 가장 높은 쪽."""
    teams = [
        r
        for r in state.relations_of(subject)
        if r.kind == RelationKind.TAG_TEAM
        and (p := state.find(r.other(subject))) is not None
        and p.bookable
    ]
    if not teams:
        return None
    return max(teams, key=lambda r: r.heat).other(subject)


def top_rival(state: WorldState, subject: str) -> str | None:
    """가장 끓는 라이벌. 대진 생성이 이걸 본다."""
    rivals = [
        r
        for r in state.relations_of(subject)
        if r.kind == RelationKind.RIVAL
        and r.a == subject
        and (o := state.find(r.other(subject))) is not None
        and o.bookable
    ]
    if not rivals:
        return None
    return max(rivals, key=lambda r: r.heat).other(subject)


def drop_retired(state: WorldState) -> WorldState:
    """은퇴 선수의 관계를 **지우지 않는다** — 읽기 전용으로 남긴다.

    함수가 아무것도 하지 않는 것이 의도다. 사용자 요구 §5 가 "은퇴 선수의 과거
    라이벌 관계 및 경기 기록 조회" 를 요구하므로 삭제가 금지된다. 호출부가
    "은퇴했으니 정리해야 하나" 를 고민하지 않게 이름을 남겨 둔다 —
    `candidates` 가 은퇴 선수를 건너뛰는 것으로 충분하다.
    """
    return state
