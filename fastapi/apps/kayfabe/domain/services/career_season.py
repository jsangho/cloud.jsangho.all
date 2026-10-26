"""시즌. **52주 → 결산 → 다음 시즌**, 세 단계가 갈라져 있다.

사용자 요구 §1. `career_run` 의 40주는 커리어의 **끝**이었다 — 넘기면 은퇴였다.
이번 52주는 **시즌의 끝**이고 커리어는 이어진다. 그래서 단계가 셋이다:

    IN_SEASON   1~52주. 주차 진행이 된다
    SETTLEMENT  52주를 처리했다. 주차 진행이 막히고 결산만 된다
    OFFSEASON   결산이 끝났다. 다음 시즌 시작만 된다

셋을 한 호출로 묶지 않은 이유는 둘이다. 첫째, "결산은 봤지만 다음 시즌은 아직"
상태가 화면에 필요하다. 둘째, **중복 방지를 한 곳에 쓸 수 있다** — 각 전이가
`applied` 에 키를 하나 남기므로 몇 번 호출되어도 한 번만 일어난다.

## 나이는 결산에서만 오른다

그래서 **결산이 재시도되어도 나이가 두 번 오르지 않는다**(§1 · §2 요구).
주차 진행은 나이를 아예 건드리지 않는다. 52주가 1년이다.

## 은퇴해도 세계는 남는다

결산이 "마지막 시즌" 의사를 확정으로 바꾸고, 은퇴한 챔피언의 벨트를 공석으로
만든다. **선수 행은 지우지 않는다**(§3.4 · §5) — 상태만 `RETIRED` 가 되고 과거
전적·관계·타이틀 기록은 그대로 조회된다.
"""

from __future__ import annotations

from dataclasses import replace

from kayfabe.domain.services.career_aging import ability_delta, age_one_season
from kayfabe.domain.services.career_retirement import assess, confirm, infer_cause
from kayfabe.domain.services.career_world import (
    AbilitySnapshot,
    Balance,
    LogEntry,
    Phase,
    RetirementCause,
    SeasonSummary,
    Title,
    WorldState,
)


def settle_key(season: int) -> str:
    return f"settle:s{season}"


def start_key(season: int) -> str:
    return f"season_start:s{season}"


def is_season_over(state: WorldState, balance: Balance) -> bool:
    """52주를 다 썼는가."""
    return state.week > balance.season_weeks


def vacate_titles_of(state: WorldState, name: str, *, reason: str) -> WorldState:
    """그 선수가 들고 있던 벨트를 **공석으로** 만든다.

    §3.4 — "은퇴 선수가 타이틀을 보유하고 있었다면 벨트를 공석으로 만들거나 별도의
    처리 이벤트를 발생시킨다." 공석 쪽을 골랐다 — 후계자를 즉시 정하면 그 경기가
    일어나지 않은 채 챔피언이 생긴다.

    **멱등이다.** 이미 그 선수가 안 들고 있으면 아무 일도 하지 않는다. 그래서 같은
    은퇴가 반복 처리되어도 벨트가 두 번 비워지지 않는다(§3.4 중복 실행 방지).
    """
    held = [t for t in state.titles if t.holder == name]
    if not held:
        return state
    titles = tuple(
        replace(t, holder=None, defenses=0, won_week=None) if t.holder == name else t
        for t in state.titles
    )
    log = state.log + tuple(
        LogEntry(
            season=state.season,
            week=state.week,
            kind="title_vacated",
            subject=name,
            title=t.name,
            summary=f"{t.name} 공석 — {reason}",
        )
        for t in held
    )
    return replace(state, titles=titles, log=log)


def enter_settlement(state: WorldState) -> WorldState:
    """52주를 처리했음을 표시한다. 주차 진행이 이 뒤로 막힌다."""
    if state.phase in (Phase.SETTLEMENT, Phase.OFFSEASON, Phase.ENDED):
        return state
    return replace(state, phase=Phase.SETTLEMENT)


def _season_log(state: WorldState, season: int) -> tuple[LogEntry, ...]:
    return tuple(e for e in state.log if e.season == season)


def _highlights(entries: tuple[LogEntry, ...]) -> tuple[str, ...]:
    """시즌의 주요 순간. **로그에서 뽑는다 — 새로 쓰지 않는다.**

    타이틀 획득·은퇴·배신만 센다. 전부 넣으면 52줄이 되고 그건 요약이 아니다.
    """
    keep = ("title_won", "retired", "title_vacated", "promoted")
    return tuple(e.summary for e in entries if e.kind in keep)[:8]


def settle(state: WorldState, *, balance: Balance) -> WorldState:
    """시즌 결산. **한 번만 일어난다.**

    하는 일 넷:
      1. 시즌 통계를 모아 `SeasonSummary` 를 남긴다
      2. "마지막 시즌" 의사를 **은퇴 확정**으로 바꾼다
      3. 로스터 전원을 한 살 늙린다(능력치는 일괄 하락이 아니다)
      4. 은퇴자의 벨트를 공석으로 만든다

    순서가 규칙이다 — 결산 통계는 **늙기 전** 나이를 적어야 하고(§6 "시즌 종료
    당시 선수 나이"), 은퇴 확정은 늙기 전에 해야 은퇴 나이가 시즌 종료 나이와 맞다.
    """
    key = settle_key(state.season)
    if key in state.applied:
        return state
    if state.phase not in (Phase.SETTLEMENT, Phase.ENDED):
        raise ValueError(f"결산할 단계가 아닙니다: {state.phase}")

    season = state.season
    entries = _season_log(state, season)
    hero_before = state.hero

    # ── 2) 마지막 시즌 선언을 확정으로 ─────────────────────────
    retired_now: list[str] = []
    roster = []
    for w in state.roster:
        if (
            not w.retired
            and w.intent is not None
            and w.intent.final_season
            and w.intent.season <= season
        ):
            risk = assess(w, balance)
            cause = (
                RetirementCause.VOLUNTARY
                if w.intent.origin == "self"
                else infer_cause(w, risk, balance)
            )
            w = confirm(
                w,
                cause=cause,
                season=season,
                week=balance.season_weeks,
                note="마지막 시즌",
            )
            retired_now.append(w.name)
        roster.append(w)
    state = replace(state, roster=tuple(roster))

    # ── 1) 통계 ────────────────────────────────────────────────
    wins = sum(1 for e in entries if e.kind == "match" and e.result == "win")
    losses = sum(1 for e in entries if e.kind == "match" and e.result == "loss")
    # **플레이어가 딴 것만 센다.** `title_won` 로그는 NPC 가 벨트를 가져간 경우에도
    # 남는다(방어에 실패하면 승자 이름으로 한 줄이 생긴다). 걸러내지 않으면 결산이
    # 빼앗긴 벨트를 "획득" 으로 적는다 — 첫 시험 런이 재위 3회에 획득 5건을 보고했다.
    titles_won = tuple(
        e.title
        for e in entries
        if e.kind == "title_won" and e.title and e.subject == state.player
    )
    defenses = sum(1 for e in entries if e.kind == "title_defended")
    injuries = sum(1 for e in entries if e.kind == "injury")
    # 시즌 **시작** 때의 능력치. 스냅샷은 시즌 시작에서만 찍으므로
    # (`create_world` · `start_next_season`) `trend[-1]` 이 이번 시즌의 출발점이다.
    #
    # 처음엔 결산에서 스냅샷을 찍고 같은 값과 비교했다 — 그래서 변화량이 **항상
    # 0** 이었다(첫 시험 런이 `delta Ability(0,0,0,0)` 로 잡았다). 찍는 시점을
    # 시즌 시작으로 옮겨서 고쳤다.
    start_ability = (
        hero_before.trend[-1].ability if hero_before.trend else hero_before.ability
    )
    season_retired = tuple(
        sorted(
            {
                *retired_now,
                *(
                    w.name
                    for w in state.roster
                    if w.retirement is not None and w.retirement.season == season
                ),
            }
        )
    )
    summary = SeasonSummary(
        season=season,
        wins=wins,
        losses=losses,
        # **늙기 전** 나이다.
        age=hero_before.age,
        ability=hero_before.ability,
        ability_delta=ability_delta(start_ability, hero_before.ability),
        titles_won=titles_won,
        defenses=defenses,
        injuries=injuries,
        retired=season_retired,
        highlights=_highlights(entries),
        risk_band=assess(hero_before, balance).band,
    )

    # ── 4) 은퇴자 벨트 공석 ────────────────────────────────────
    for name in season_retired:
        state = vacate_titles_of(state, name, reason="은퇴")

    # ── 3) 노화 ────────────────────────────────────────────────
    # **결산은 스냅샷을 찍지 않는다.** 찍는 곳은 시즌 시작 한 곳이다 — 두 곳에서
    # 찍으면 시즌당 두 칸이 쌓여 `recent_trend` 가 "같은 시즌 안의 변화" 를 재게 된다.
    aged = tuple(
        age_one_season(w, seed=state.seed, balance=balance, season=season)
        for w in state.roster
    )

    phase = Phase.ENDED if state.require(state.player).retired else Phase.OFFSEASON
    return replace(
        state,
        roster=aged,
        seasons=state.seasons + (summary,),
        phase=phase,
        applied=state.applied | {key},
        log=state.log
        + (
            LogEntry(
                season=season,
                week=balance.season_weeks,
                kind="season_end",
                subject=state.player,
                summary=f"시즌 {season} 결산 — {wins}승 {losses}패",
            ),
        ),
    )


def start_next_season(state: WorldState, *, balance: Balance) -> WorldState:
    """다음 시즌을 시작한다. **주차만 1로 돌아가고 나머지는 전부 남는다.**

    §1 — "다음 시즌에서도 선수 능력치, 나이, 전적, 관계, 타이틀 이력, 부상 이력,
    은퇴 상태 및 커리어 기록을 보존한다." 그래서 여기서 초기화하는 것은 `week` ·
    `action_points` · `pending` 셋뿐이다.

    `pending` 을 비우는 것은 의도다 — 지난 시즌 52주의 사건을 새 시즌 1주에 들고
    가면 주차가 안 맞는다. 해결되지 않은 사건은 조건이 그대로면 다시 열린다.

    **한 번만 일어난다**(멱등 키). 플레이어가 은퇴했으면 거부한다.
    """
    # **이미 시작한 시즌인지 먼저 본다.** `start_key(state.season + 1)` 로 재면
    # 전이가 끝난 뒤 `season` 이 올라가 있어 **다음다음 시즌의 키**를 보게 되고,
    # 그러면 두 번째 호출이 멱등이 아니라 `ValueError` 를 낸다(첫 시험 런이 잡았다).
    # 기준은 "지금 시즌이 이미 시작됐는가" 다.
    if start_key(state.season) in state.applied and state.phase == Phase.IN_SEASON:
        return state

    target = state.season + 1
    key = start_key(target)
    if key in state.applied:
        return state
    if state.phase == Phase.ENDED:
        raise ValueError("플레이어가 은퇴해 다음 시즌을 시작할 수 없습니다")
    if state.phase != Phase.OFFSEASON:
        raise ValueError(f"다음 시즌을 시작할 단계가 아닙니다: {state.phase}")

    # 연속 출전 부담은 시즌이 끝나면 풀린다 — 오프시즌이 그 역할이다.
    # **능력치 스냅샷을 여기서 찍는다** — 시즌의 출발점이고, 결산이 변화량을
    # 이 값과 비교한다.
    roster = tuple(
        replace(
            w,
            consecutive_matches=0,
            condition=min(100, w.condition + 12),
            trend=(
                w.trend
                + (AbilitySnapshot(season=target, age=w.age, ability=w.ability),)
            )[-12:],
        )
        if not w.retired
        else w
        for w in state.roster
    )
    return replace(
        state,
        season=target,
        week=1,
        phase=Phase.IN_SEASON,
        action_points=balance.action_points,
        roster=roster,
        pending=(),
        applied=state.applied | {key},
        log=state.log
        + (
            LogEntry(
                season=target,
                week=1,
                kind="season_start",
                subject=state.player,
                summary=f"시즌 {target} 시작",
            ),
        ),
    )


def default_titles() -> tuple[Title, ...]:
    """기본 벨트 넷. `career_run` 의 사다리를 이었고 태그를 하나 더했다.

    요구 인기도가 사다리의 단계를 만든다 — NXT 40 · IC 65 · 월챔 85.
    """
    return (
        Title(name="NXT Championship", brand="NXT", required_popularity=40),
        Title(
            name="Intercontinental Championship", brand="Raw", required_popularity=65
        ),
        Title(
            name="World Heavyweight Championship",
            brand="SmackDown",
            required_popularity=85,
        ),
        Title(name="Tag Team Championship", brand="Raw", required_popularity=50),
    )
