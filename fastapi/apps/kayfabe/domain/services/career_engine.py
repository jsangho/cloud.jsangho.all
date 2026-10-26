"""커리어 엔진. **한 주를 넘기는 것이 이 파일의 전부다.**

규칙의 조립만 한다 — 부상·노화·은퇴·관계·사건·경기는 각자의 파일에 있고 여기서는
순서만 정한다. 순서가 규칙인 자리가 셋 있어서 주석으로 적어 뒀다.

## 결정론

주차 진행은 `(seed, season, week)` 에서만 뽑기를 한다. 같은 세계·같은 주차면
**몇 번 호출해도 같은 결과**이고, 멱등 키(`week:sNwM`)가 **같은 세이브에 대한**
두 번째 적용을 아예 막는다(사용자 요구 §P0 경기 — 멱등성 · §7 검증 8).

**요청 단위 멱등성은 아니다.** 저장이 끝난 뒤 같은 요청이 다시 들어오면 그
세이브의 주차가 이미 넘어가 있으므로 **다음 주**가 진행된다 — 서버가 "재시도" 와
"한 주 더" 를 구별할 근거가 없기 때문이다(구별하려면 요청에 클라이언트 키가
필요하다). 동시 요청 둘이 전적을 두 번 올리는 것을 막는 쪽은 이 키가 아니라
저장 계층의 행 잠금이다(`load_for_update`).

## AI 가 없다

주간 진행에 AI 호출이 없다. 사용자 요구 §2.3 — "AI 의 자연어 응답을 파싱해 경기
결과나 핵심 DB 상태를 결정하지 않는다. AI API 가 실패하거나 응답이 지연되어도
핵심 게임 진행은 정상적으로 저장되어야 한다." 그래서 서술은 `LogEntry.summary` 에
사실로만 적고, 산문이 필요하면 확정된 상태를 읽어 나중에 만든다.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from kayfabe.domain.services import career_events as events
from kayfabe.domain.services import career_relations as relations
from kayfabe.domain.services import career_retirement as retire
from kayfabe.domain.services import career_season as season_rules
from kayfabe.domain.services.career_actions import reset_points
from kayfabe.domain.services.career_injury import maybe_injure, tick_recovery
from kayfabe.domain.services.career_match import (
    MATCH_TAG,
    MatchOutcome,
    simulate_single,
    simulate_tag,
)
from kayfabe.domain.services.career_rng import pick, roll
from kayfabe.domain.services.career_world import (
    Ability,
    AbilitySnapshot,
    Alignment,
    Balance,
    LogEntry,
    Phase,
    Title,
    WorldState,
    Wrestler,
)

#: 같은 상대를 연달아 붙이지 않는 창. **대진 반복 방지**(§P1).
REMATCH_WINDOW = 3

#: 로그 보관 상한. **세이브가 무한히 커지는 것을 막는다** — 실측으로 4시즌에
#: 884줄이었고(주당 ~4줄) 세이브는 JSON 한 칸이다. 10시즌이면 2천 줄이 한 행에
#: 들어간다.
#:
#: 오래된 줄을 버려도 **장기 기록은 남는다** — 시즌별 결산(`SeasonSummary`)이
#: 따로 쌓이고 그쪽은 시즌당 한 장이라 자라지 않는다. 버리는 것은 주차 단위
#: 상세이고 요약은 보존된다.
MAX_LOG = 1200


def week_key(*, season: int, week: int) -> str:
    return f"week:s{season}w{week}"


@dataclass(frozen=True)
class Card:
    """이번 주 대진. 경기가 없으면 `kind == "rest"`."""

    kind: str
    opponent: str | None = None
    title: str | None = None
    partner: str | None = None
    opponents: tuple[str, ...] = ()
    note: str = ""


@dataclass(frozen=True)
class WeekReport:
    """그 주에 **일어난 일만**. 문장은 화면이 만든다."""

    season: int
    week: int
    kind: str
    opponent: str | None = None
    won: bool | None = None
    title: str | None = None
    title_changed: bool = False
    finish: str | None = None
    rating: int = 0
    popularity_delta: int = 0
    injured: str | None = None
    injured_weeks: int = 0
    promoted_to: str | None = None
    opened_events: tuple[str, ...] = ()
    retired: bool = False
    risk_band: str = ""
    probability: float = 0.0


@dataclass(frozen=True)
class WeekResult:
    state: WorldState
    report: WeekReport


# ── 세계 만들기 ───────────────────────────────────────────────────

#: 기본 NPC 로스터. **이름은 가상이다** — 실제 선수 데이터는 `DataCenterRepository`
#: 가 주고, 그쪽을 쓸 때는 `create_world(roster=...)` 로 넣는다.
_NPC_SEED = (
    ("Dex Harlow", "파워", "NXT", 26, 52, 48),
    ("Marcus Vane", "테크니션", "NXT", 29, 58, 55),
    ("Rio Castellan", "하이플라이어", "NXT", 24, 45, 42),
    ("Bastian Kord", "파워", "Raw", 33, 71, 68),
    ("Oren Welles", "테크니션", "Raw", 31, 66, 72),
    ("Kit Sorrow", "하이플라이어", "Raw", 27, 63, 59),
    ("Silas Grimm", "파워", "SmackDown", 36, 78, 70),
    ("Noor Haddad", "테크니션", "SmackDown", 30, 74, 76),
    ("Jae Pyun", "하이플라이어", "SmackDown", 25, 61, 57),
)


def default_roster() -> tuple[Wrestler, ...]:
    """기본 NPC 아홉. 브랜드별 셋이라 대진이 늘 성립한다."""
    return tuple(
        Wrestler(
            name=name,
            style=style,
            brand=brand,
            age=age,
            debut_age=age - 3,
            popularity=pop,
            ability=Ability(in_ring=skill, mic=skill - 8, stamina=78, resilience=74),
            alignment=Alignment.HEEL if idx % 3 == 0 else Alignment.FACE,
            trend=(
                AbilitySnapshot(
                    season=1,
                    age=age,
                    ability=Ability(
                        in_ring=skill, mic=skill - 8, stamina=78, resilience=74
                    ),
                ),
            ),
        )
        for idx, (name, style, brand, age, pop, skill) in enumerate(_NPC_SEED)
    )


def create_world(
    *,
    player: str,
    style: str,
    seed: int,
    age: int = 24,
    balance: Balance | None = None,
    roster: tuple[Wrestler, ...] | None = None,
    titles: tuple[Title, ...] | None = None,
) -> WorldState:
    """새 세계. **플레이어는 NXT 에서 시작한다.**

    나이를 인수로 받는 것은 §2 의 "커리어 시작 시 나이" 다 — `debut_age` 에 같은
    값이 들어가고 그 뒤 바뀌지 않는다.
    """
    bal = balance or Balance()
    if not player.strip():
        raise ValueError("링네임이 필요합니다")
    if not (bal.min_debut_age <= age <= bal.max_debut_age):
        raise ValueError(f"데뷔 나이는 {bal.min_debut_age}~{bal.max_debut_age}세")

    debut_ability = Ability(in_ring=38, mic=35, stamina=82, resilience=80)
    hero = Wrestler(
        name=player.strip(),
        style=style,
        brand="NXT",
        age=age,
        debut_age=age,
        popularity=20,
        ability=debut_ability,
        condition=85,
        is_player=True,
        # **시즌 1의 출발점 스냅샷.** 결산이 변화량을 이 값과 비교한다 — 없으면
        # 첫 시즌의 능력치 변화가 0으로 보고된다.
        trend=(AbilitySnapshot(season=1, age=age, ability=debut_ability),),
    )
    npcs = tuple(
        w
        for w in (roster if roster is not None else default_roster())
        if w.name != hero.name
    )
    return WorldState(
        seed=seed,
        player=hero.name,
        season=1,
        week=1,
        phase=Phase.IN_SEASON,
        action_points=bal.action_points,
        roster=(hero,) + npcs,
        titles=titles if titles is not None else season_rules.default_titles(),
        log=(
            LogEntry(
                season=1,
                week=1,
                kind="debut",
                subject=hero.name,
                summary=f"{hero.name} 데뷔 — {style} · {age}세 · NXT",
            ),
        ),
    )


# ── 대진 ──────────────────────────────────────────────────────────


def _recent_opponents(state: WorldState) -> tuple[str, ...]:
    """최근 상대들. **같은 상대 연속 배정을 막는다**(§P1)."""
    found: list[str] = []
    for entry in reversed(state.log):
        if entry.kind == "match" and entry.other:
            found.append(entry.other)
        if len(found) >= REMATCH_WINDOW:
            break
    return tuple(found)


def _title_for(state: WorldState, me: Wrestler) -> Title | None:
    """이번 주 타이틀전의 벨트. 없으면 `None`.

    **들고 있으면 방어가 먼저다.** 아니면 도전권이 있거나 인기도가 자격에 닿은
    브랜드 벨트 중 가장 높은 것.
    """
    held = state.title_held_by(me.name)
    if held:
        return held[0]
    has_shot = f"shot:s{state.season}w{state.week}" in state.applied
    open_belts = [
        t
        for t in state.titles
        if t.brand == me.brand and me.popularity >= t.required_popularity
    ]
    if not open_belts:
        return None
    belt = max(open_belts, key=lambda t: t.required_popularity)
    if has_shot:
        return belt
    # 도전권이 없으면 공석일 때만 자동으로 선다 — 챔피언이 있으면 제안·협상을 거친다.
    return belt if belt.vacant else None


def book(state: WorldState, *, balance: Balance) -> Card:
    """이번 주 대진을 짠다. **은퇴·부상자는 후보에서 빠진다**(§3.4).

    우선순위: 타이틀전 → 태그 → 라이벌전 → 일반. 하나만 선다 —
    **타이틀전과 다른 경기를 같은 주에 겹쳐 넣지 않는다**(§P1 중복 배정 방지).
    """
    me = state.require(state.player)
    if me.retired:
        return Card(kind="rest", note="은퇴")
    if me.out_weeks > 0:
        return Card(kind="rest", note="부상 결장")

    pool = tuple(
        w.name
        for w in state.roster
        if w.name != me.name and w.bookable and w.brand == me.brand
    )
    if not pool:
        pool = tuple(w.name for w in state.roster if w.name != me.name and w.bookable)
    if not pool:
        return Card(kind="rest", note="상대가 없다")

    recent = _recent_opponents(state)
    fresh = tuple(n for n in pool if n not in recent) or pool

    # 1) 타이틀전.
    belt = _title_for(state, me)
    if belt is not None:
        champ = belt.holder
        if champ == me.name:
            challenger = pick(state.seed, fresh, "challenger", state.season, state.week)
            if challenger:
                return Card(
                    kind="title", opponent=challenger, title=belt.name, note="방어전"
                )
        else:
            opponent = champ if champ in pool else None
            if opponent is None and belt.vacant:
                opponent = pick(state.seed, fresh, "vacant", state.season, state.week)
            if opponent:
                return Card(
                    kind="title", opponent=opponent, title=belt.name, note="도전"
                )

    # 2) 태그팀.
    partner = relations.tag_partner(state, me.name)
    if partner:
        foes = tuple(n for n in pool if n != partner)
        if len(foes) >= 2:
            first = pick(state.seed, foes, "tagfoe1", state.season, state.week)
            rest_foes = tuple(n for n in foes if n != first)
            second = pick(state.seed, rest_foes, "tagfoe2", state.season, state.week)
            if first and second:
                return Card(
                    kind="tag",
                    partner=partner,
                    opponents=(first, second),
                    opponent=first,
                    note="태그팀",
                )

    # 3) 라이벌전.
    rival = relations.top_rival(state, me.name)
    if rival and rival in pool and rival not in recent[:1]:
        return Card(kind="single", opponent=rival, note="라이벌전")

    # 4) 일반.
    opponent = pick(state.seed, fresh, "opponent", state.season, state.week)
    return Card(kind="single", opponent=opponent, note="일반 경기")


# ── 주차 진행 ─────────────────────────────────────────────────────


def _put(state: WorldState, w: Wrestler) -> WorldState:
    return replace(
        state, roster=tuple(x if x.name != w.name else w for x in state.roster)
    )


def _award_title(
    state: WorldState, *, belt: str, winner: str, absolute_week: int
) -> WorldState:
    """벨트 주인을 바꾼다. 역대 기록은 **획득할 때만** 늘어난다."""
    titles = tuple(
        replace(t, holder=winner, defenses=0, won_week=absolute_week)
        if t.name == belt
        else t
        for t in state.titles
    )
    champ = state.require(winner)
    champ = replace(
        champ,
        held=tuple(dict.fromkeys(champ.held + (belt,))),
        reigns=champ.reigns + (belt,),
    )
    return _put(replace(state, titles=titles), champ)


def _strip_title(state: WorldState, *, belt: str, former: str) -> WorldState:
    champ = state.find(former)
    if champ is None:
        return state
    return _put(state, replace(champ, held=tuple(b for b in champ.held if b != belt)))


def _apply_outcome(
    state: WorldState, *, outcome: MatchOutcome, card: Card, balance: Balance
) -> tuple[WorldState, WeekReport]:
    """경기 결과를 세계에 반영한다. **전적·인기도·벨트·관계가 여기서 움직인다.**"""
    me = state.require(state.player)
    won = outcome.winner == me.name or (
        outcome.kind == MATCH_TAG
        and me.name
        in (outcome.team_a if outcome.winner in outcome.team_a else outcome.team_b)
    )
    title_match = card.title is not None
    defending = title_match and card.title in me.held

    # 인기도 — 경기 평가가 폭을 키운다.
    if defending:
        base = 7 if won else -8
    elif title_match:
        base = 14 if won else -8
    else:
        base = 8 if won else -3
    bonus = (outcome.rating - 50) // 12
    delta = base + (bonus if won else 0)
    if won:
        delta += {"파워": 0, "테크니션": 1, "하이플라이어": 3}.get(me.style, 0)

    popularity = max(
        balance.min_popularity, min(balance.max_popularity, me.popularity + delta)
    )
    me = replace(
        me,
        wins=me.wins + (1 if won else 0),
        losses=me.losses + (0 if won else 1),
        losing_streak=0 if won else me.losing_streak + 1,
        popularity=popularity,
        condition=max(10, me.condition - 10),
        consecutive_matches=me.consecutive_matches + 1,
    )
    state = _put(state, me)

    # 벨트.
    title_changed = False
    absolute = (state.season - 1) * balance.season_weeks + state.week
    if title_match and card.title:
        belt = next((t for t in state.titles if t.name == card.title), None)
        if belt is not None:
            if defending:
                if won:
                    state = replace(
                        state,
                        titles=tuple(
                            replace(t, defenses=t.defenses + 1)
                            if t.name == belt.name
                            else t
                            for t in state.titles
                        ),
                    )
                else:
                    state = _strip_title(state, belt=belt.name, former=me.name)
                    state = _award_title(
                        state,
                        belt=belt.name,
                        winner=outcome.winner,
                        absolute_week=absolute,
                    )
                    title_changed = True
            elif won:
                if belt.holder:
                    state = _strip_title(state, belt=belt.name, former=belt.holder)
                state = _award_title(
                    state, belt=belt.name, winner=me.name, absolute_week=absolute
                )
                title_changed = True

    # 상대 전적.
    foe_name = outcome.loser if outcome.winner == me.name else outcome.winner
    foe = state.find(foe_name)
    if foe is not None and foe.name != me.name:
        foe = replace(
            foe,
            wins=foe.wins + (0 if won else 1),
            losses=foe.losses + (1 if won else 0),
            losing_streak=0 if not won else foe.losing_streak + 1,
            condition=max(10, foe.condition - 8),
            consecutive_matches=foe.consecutive_matches + 1,
        )
        state = _put(state, foe)

    # 관계.
    if card.opponent:
        state = relations.after_match(
            state,
            winner=outcome.winner,
            loser=outcome.loser,
            week=state.week,
            title_match=title_match,
        )

    kind_label = (
        "방어전"
        if defending
        else ("타이틀전" if title_match else ("태그" if card.kind == "tag" else "경기"))
    )
    state = replace(
        state,
        log=state.log
        + (
            LogEntry(
                season=state.season,
                week=state.week,
                kind="match",
                subject=me.name,
                other=card.opponent,
                result="win" if won else "loss",
                title=card.title,
                summary=(
                    f"{kind_label} vs {card.opponent} — {'승' if won else '패'}"
                    f" ({outcome.finish} · 평가 {outcome.rating})"
                ),
            ),
        ),
    )
    if title_changed:
        state = replace(
            state,
            log=state.log
            + (
                LogEntry(
                    season=state.season,
                    week=state.week,
                    kind="title_won",
                    subject=outcome.winner if not defending else outcome.winner,
                    title=card.title,
                    summary=f"{card.title} 획득 — {outcome.winner}",
                ),
            ),
        )
    elif defending and won:
        state = replace(
            state,
            log=state.log
            + (
                LogEntry(
                    season=state.season,
                    week=state.week,
                    kind="title_defended",
                    subject=me.name,
                    title=card.title,
                    summary=f"{card.title} 방어 성공",
                ),
            ),
        )

    report = WeekReport(
        season=state.season,
        week=state.week,
        kind=kind_label,
        opponent=card.opponent,
        won=won,
        title=card.title,
        title_changed=title_changed,
        finish=outcome.finish,
        rating=outcome.rating,
        popularity_delta=delta,
        probability=outcome.probability,
    )
    return state, report


def advance_week(state: WorldState, *, balance: Balance | None = None) -> WeekResult:
    """한 주를 넘긴다. **멱등이다** — 같은 주차를 두 번 진행할 수 없다.

    순서가 규칙인 자리 셋:

    1. **결장 소모가 경기보다 먼저다.** 뒤에 두면 다친 주에 바로 경기한다.
    2. **부상 판정이 사건 생성보다 먼저다.** 뒤에 두면 "심각한 부상 뒤 결정"
       사건이 그 주에 못 열리고 한 주 늦는다.
    3. **승격이 경기 뒤다.** 경기로 오른 인기도가 그 주에 반영되어야 한다.
    """
    bal = balance or Balance()

    if state.phase == Phase.ENDED:
        return WeekResult(
            state, WeekReport(season=state.season, week=state.week, kind="종료")
        )
    if state.phase != Phase.IN_SEASON:
        raise ValueError(
            f"주차를 진행할 단계가 아닙니다: {state.phase} — 결산이 먼저입니다"
        )

    key = week_key(season=state.season, week=state.week)
    if key in state.applied:
        # 이미 처리한 주차다. 아무것도 바꾸지 않는다.
        return WeekResult(
            state, WeekReport(season=state.season, week=state.week, kind="중복")
        )

    season, week = state.season, state.week
    rng_key = f"s{season}w{week}"
    me = state.require(state.player)

    # ── 1) 결장 소모 ───────────────────────────────────────────
    if me.out_weeks > 0:
        healed, back = tick_recovery(me)
        state = _put(state, healed)
        report = WeekReport(
            season=season,
            week=week,
            kind="복귀" if back else "결장",
            injured_weeks=healed.out_weeks,
            risk_band=retire.assess(healed, bal).band,
        )
        state = replace(
            state,
            log=state.log
            + (
                LogEntry(
                    season=season,
                    week=week,
                    kind="out",
                    subject=me.name,
                    summary=(
                        "부상에서 복귀했다"
                        if back
                        else f"결장 — {healed.out_weeks}주 남음"
                    ),
                ),
            ),
        )
        state = events.generate(state, balance=bal)
        return _close_week(state, report, bal, key)

    # ── 2) 경기 ────────────────────────────────────────────────
    card = book(state, balance=bal)
    if card.kind == "rest" or card.opponent is None:
        report = WeekReport(
            season=season, week=week, kind="휴식", risk_band=retire.assess(me, bal).band
        )
        state = replace(
            state,
            log=state.log
            + (
                LogEntry(
                    season=season,
                    week=week,
                    kind="rest",
                    subject=me.name,
                    summary=f"경기 없음 — {card.note}",
                ),
            ),
        )
        state = events.generate(state, balance=bal)
        return _close_week(state, report, bal, key)

    if card.kind == "tag" and card.partner and len(card.opponents) >= 2:
        team_a = (state.require(state.player), state.require(card.partner))
        team_b = tuple(state.require(n) for n in card.opponents)
        outcome = simulate_tag(team_a, team_b, seed=state.seed, key=rng_key)
    else:
        foe = state.require(card.opponent)
        challenger = None
        if card.title:
            belt = next((t for t in state.titles if t.name == card.title), None)
            if belt is not None:
                challenger = (
                    state.player if belt.holder != state.player else card.opponent
                )
        outcome = simulate_single(
            state.require(state.player),
            foe,
            seed=state.seed,
            key=rng_key,
            title=card.title,
            challenger=challenger,
        )

    state, report = _apply_outcome(state, outcome=outcome, card=card, balance=bal)

    # ── 3) 부상 판정 ───────────────────────────────────────────
    me = state.require(state.player)
    hurt, injury = maybe_injure(
        me, seed=state.seed, balance=bal, season=season, week=week, key=rng_key
    )
    if injury is not None:
        state = _put(state, hurt)
        state = replace(
            state,
            log=state.log
            + (
                LogEntry(
                    season=season,
                    week=week,
                    kind="injury",
                    subject=me.name,
                    summary=(
                        f"{injury.kind} {injury.severity} 부상 — {injury.weeks_out}주 결장"
                        + (" (재발)" if injury.recurrence else "")
                    ),
                ),
            ),
        )
        report = replace(report, injured=injury.kind, injured_weeks=injury.weeks_out)

    # ── 4) 승격 ────────────────────────────────────────────────
    me = state.require(state.player)
    if me.brand == "NXT" and me.popularity >= bal.promotion_popularity:
        brand = "Raw" if roll(state.seed, rng_key, "brand") < 0.5 else "SmackDown"
        state = _put(state, replace(me, brand=brand))
        state = replace(
            state,
            log=state.log
            + (
                LogEntry(
                    season=season,
                    week=week,
                    kind="promoted",
                    subject=me.name,
                    summary=f"메인 로스터 승격 — {brand}",
                ),
            ),
        )
        report = replace(report, promoted_to=brand)

    # ── 5) 사건 ────────────────────────────────────────────────
    before = {e.id for e in state.pending}
    state = events.generate(state, balance=bal)
    opened = tuple(e.headline for e in state.pending if e.id not in before)
    report = replace(report, opened_events=opened)

    return _close_week(state, report, bal, key)


def _close_week(
    state: WorldState, report: WeekReport, balance: Balance, key: str
) -> WeekResult:
    """주차를 닫는다. **자동 은퇴 판정과 시즌 경계가 여기서 일어난다.**

    자동 은퇴는 `should_auto_retire` 가 요구하는 두 자물쇠를 통과해야 한다 —
    점수와 의사. 의학적 영구 불가만 예외다.
    """
    me = state.require(state.player)
    risk = retire.assess(me, balance)
    report = replace(report, risk_band=risk.band)

    if not me.retired and retire.should_auto_retire(me, risk, balance):
        cause = retire.infer_cause(me, risk, balance)
        state = _put(
            state,
            retire.confirm(
                me, cause=cause, season=state.season, week=state.week, note=risk.band
            ),
        )
        state = season_rules.vacate_titles_of(state, me.name, reason="은퇴")
        state = replace(
            state,
            log=state.log
            + (
                LogEntry(
                    season=state.season,
                    week=state.week,
                    kind="retired",
                    subject=me.name,
                    summary=f"은퇴 — {cause}",
                ),
            ),
        )
        report = replace(report, retired=True)

    # 주차를 넘기고 포인트를 채운다. 로그는 상한에서 자른다.
    state = reset_points(
        replace(
            state,
            week=state.week + 1,
            applied=state.applied | {key},
            log=state.log[-MAX_LOG:],
        ),
        balance,
    )

    # 플레이어가 은퇴했으면 세계를 닫는다 — 결산을 거쳐야 기록이 남는다.
    if state.require(state.player).retired:
        state = replace(state, phase=Phase.SETTLEMENT)
    elif season_rules.is_season_over(state, balance):
        state = season_rules.enter_settlement(state)

    return WeekResult(state, report)
