"""`WorldState` ↔ JSON. **저장 계층이 규칙을 모르게 하는 경계다.**

도메인은 `sqlalchemy` 를 import 하지 않고, 저장 계층은 규칙을 import 하지 않는다.
그 사이를 잇는 것이 이 파일 하나다 — 세계를 통째로 dict 로 눕히고 되살린다.

## 왜 통째로 눕히나

이전 커리어 시뮬레이터는 세이브 하나를 **다섯 표**에 나눠 넣었고(`career_runs` ·
`career_rivalries` · `career_log_entries` · `career_seen_events` ·
`career_trophies`), 그 마이그레이션이 **열두 개**로 불어났다 — 칸을 하나 더할
때마다 ALTER 가 하나씩 붙었다. 그 표들은 아직 DB 에 남아 있다.

진행 한 번이 세이브를 통째로 다시 쓰므로 표로 쪼갤 이유가 없다. 그래서 JSON 한
칸이고, **게임 규칙이 늘어도 스키마가 그대로**다. 조회 단위로 필요한 것만
(`season`·`week`·`phase`) 별도 칼럼으로 뺀다 — 목록 화면이 JSON 을 열지 않도록.

## 버전 칸은 둔다

`SCHEMA_VERSION` 하나다. 세이브 모양이 바뀌면 숫자가 오르고, 모르는 버전은
**조용히 읽지 않고 거부한다** — 조용히 읽으면 빈 칸이 기본값으로 채워져 전적이
0이 된 세이브가 정상처럼 보인다.

**아는 옛 판본은 읽을 때 올린다**(`_UPGRADES`). 업그레이드는 메모리에서만 일어나고
DB 는 건드리지 않는다 — 다음 정상 저장(`dump`)이 새 판본으로 쓴다. 조회만 하는
경로(`GET`)는 저장하지 않으므로 옛 판본 행이 그대로 남아도 정상이다. 일괄 변환
스크립트를 두지 않는 이유다.

업그레이드 함수는 **옛 칸을 하나도 바꾸지 않고 새 칸만 더한다.** 새 칸의 값을 옛
기록으로 정확히 셀 수 없으면 추정하지 않고 "여기부터 셌다" 를 적는다
(`_upgrade_v1_to_v2` · `_upgrade_v2_to_v3`). 판본은 한 단계씩 오른다 — v1 세이브는
v1 → v2 → v3 를 차례로 지난다.

## `mappers/` 가 아니라 `pg/` 에 있는 이유

`mappers/__init__.py` 가 `ple_schema_mapper` → `adapter.inbound.api` →
`ple_events_router` → `ple_schema_mapper` 로 도는 **기존 순환 import** 를 들고
있다. 테스트는 다른 순서로 import 해서 안 터지지만, 이 파일을 거기 두면
`mappers` 를 먼저 import 하는 경로에서 터진다(실측). 순환은 이 작업 범위가
아니라 손대지 않고, 빈 `__init__` 을 가진 `pg/` 로 비켰다.
"""

from __future__ import annotations

from typing import Any

from kayfabe.app.ports.output.sandbox_career_repository import CorruptSaveError
from kayfabe.domain.services import career_tally as tally
from kayfabe.domain.services.career_world import (
    STATE_FIELDS,
    Ability,
    AbilitySnapshot,
    Choice,
    HeatChange,
    Injury,
    LogEntry,
    MatchRecord,
    ParticipantRecord,
    PendingEvent,
    Relationship,
    Retirement,
    RetirementIntent,
    SeasonSummary,
    Title,
    WorldState,
    Wrestler,
)

#: 세이브 모양의 판본. **칸의 뜻이 바뀌거나, 옛 세이브에 없는 칸의 값을 기본값으로
#: 메우면 틀리는 경우** 올린다 — 그 경우 업그레이드 함수가 옛 기록에서 값을 정한다.
#:
#: 1 → 2 (Phase 0): 선수에 `win_streak` · `best_win_streak` · `streaks_since`.
#: 2 → 3 (Phase 1 P0): 세계에 `matches`(경기 기록) · `match_records_since`.
SCHEMA_VERSION = 3


def _ability(d: dict[str, Any]) -> Ability:
    return Ability(
        in_ring=d["in_ring"],
        mic=d["mic"],
        stamina=d["stamina"],
        resilience=d["resilience"],
    )


def _ability_out(a: Ability) -> dict[str, Any]:
    return {
        "in_ring": a.in_ring,
        "mic": a.mic,
        "stamina": a.stamina,
        "resilience": a.resilience,
    }


def _injury_out(i: Injury) -> dict[str, Any]:
    """부상 한 건. 선수 이력과 경기 기록이 **같은 모양**을 쓴다."""
    return {
        "kind": i.kind,
        "severity": str(i.severity),
        "season": i.season,
        "week": i.week,
        "weeks_out": i.weeks_out,
        "recovered": i.recovered,
        "recurrence": i.recurrence,
        "permanent": i.permanent,
    }


def _injury_in(i: dict[str, Any]) -> Injury:
    return Injury(
        kind=i["kind"],
        severity=i["severity"],
        season=i["season"],
        week=i["week"],
        weeks_out=i["weeks_out"],
        recovered=i.get("recovered", False),
        recurrence=i.get("recurrence", False),
        permanent=i.get("permanent", False),
    )


#: 경기 기록 칸의 타입. **`type()` 으로 정확히 본다** — `bool` 은 `int` 의 하위라
#: `isinstance` 로 보면 `true` 가 주차로 통과한다.
_TEXT = (str,)
_OPTIONAL_TEXT = (str, type(None))
_INT = (int,)
_NUMBER = (int, float)
_BOOL = (bool,)
_MATCH_TYPES: dict[str, tuple[type, ...]] = {
    "id": _TEXT,
    "season": _INT,
    "week": _INT,
    "brand": _TEXT,
    "kind": _TEXT,
    "reason": _TEXT,
    "title": _OPTIONAL_TEXT,
    "title_changed": _BOOL,
    "winner_side": _INT,
    "probability": _NUMBER,
    "finish": _TEXT,
    "rating": _INT,
    "finisher": _OPTIONAL_TEXT,
    "scorer": _OPTIONAL_TEXT,
    "pinned": _OPTIONAL_TEXT,
    "popularity_delta": _INT,
}
_INJURY_TYPES: dict[str, tuple[type, ...]] = {
    "kind": _TEXT,
    "severity": _TEXT,
    "season": _INT,
    "week": _INT,
    "weeks_out": _INT,
}
_HEAT_TYPES: dict[str, tuple[type, ...]] = {
    "a": _TEXT,
    "b": _TEXT,
    "before": (int, type(None)),
    "after": _INT,
}


def _typed(d: dict[str, Any], expected: dict[str, tuple[type, ...]]) -> bool:
    return all(type(d[field]) in allowed for field, allowed in expected.items())


def _match_types_ok(d: dict[str, Any]) -> bool:
    """칸의 타입. 모양(`_match_in`)과 따로 보는 이유는 **어긋나는 지점이 달라서다.**

    타입이 틀린 기록은 데이터클래스를 그대로 통과한다. 그러면 세계가 정상으로 읽혀
    상세 화면이 200 이고, 쓰기가 손상을 다시 저장하고, 응답 스키마가 있는 `/matches`
    에서만 500 이 난다(2026-11-06 실측). 여기서 거부해야 읽기와 쓰기가 같은 판정을 본다.
    """
    injury = d["injury"]
    return (
        _typed(d, _MATCH_TYPES)
        and all(type(name) is str for team in d["teams"] for name in team)
        and all(
            type(p["name"]) is str
            and type(p["side"]) is int
            and all(type(v) in _NUMBER for v in p["power"])
            and all(type(v) is int for v in (*p["before"], *p["after"]))
            for p in d["participants"]
        )
        and all(_typed(h, _HEAT_TYPES) for h in d["heat"])
        and (injury is None or _typed(injury, _INJURY_TYPES))
    )


def _match_out(m: MatchRecord) -> dict[str, Any]:
    """경기 기록 한 장. 전후 상태는 `STATE_FIELDS` 순서의 **배열**이다(크기 때문)."""
    return {
        "id": m.id,
        "season": m.season,
        "week": m.week,
        "brand": m.brand,
        "kind": m.kind,
        "reason": m.reason,
        "title": m.title,
        "title_changed": m.title_changed,
        "teams": [list(team) for team in m.teams],
        "winner_side": m.winner_side,
        "probability": m.probability,
        "finish": m.finish,
        "rating": m.rating,
        "finisher": m.finisher,
        "scorer": m.scorer,
        "pinned": m.pinned,
        "participants": [
            {
                "name": p.name,
                "side": p.side,
                "power": list(p.power),
                "before": list(p.before),
                "after": list(p.after),
            }
            for p in m.participants
        ],
        "heat": [
            {"a": h.a, "b": h.b, "before": h.before, "after": h.after} for h in m.heat
        ],
        "injury": None if m.injury is None else _injury_out(m.injury),
        "popularity_delta": m.popularity_delta,
    }


def _match_in(d: dict[str, Any]) -> MatchRecord:
    """경기 기록을 되살린다. **모양이 어긋나면 손상이다** — 배열 길이가 하나 틀리면
    인기도가 컨디션 자리에 읽히는데, 그것은 조용히 틀린 숫자가 된다."""
    teams = tuple(tuple(team) for team in d["teams"])
    participants = tuple(
        ParticipantRecord(
            name=p["name"],
            side=p["side"],
            power=tuple(p["power"]),
            before=tuple(p["before"]),
            after=tuple(p["after"]),
        )
        for p in d["participants"]
    )
    expected = [(name, side) for side, team in enumerate(teams) for name in team]
    names = [p.name for p in participants]
    width = len(STATE_FIELDS)
    if not (
        _match_types_ok(d)
        and len(teams) == 2
        and all(teams)
        and type(d["winner_side"]) is int
        and d["winner_side"] in (0, 1)
        and [(p.name, p.side) for p in participants] == expected
        and len(set(names)) == len(names)
        and all(
            len(p.before) == width and len(p.after) == width and len(p.power) == 3
            for p in participants
        )
    ):
        raise CorruptSaveError("세이브를 되살릴 수 없습니다")
    injury = d["injury"]
    return MatchRecord(
        id=d["id"],
        season=d["season"],
        week=d["week"],
        brand=d["brand"],
        kind=d["kind"],
        reason=d["reason"],
        title=d["title"],
        title_changed=d["title_changed"],
        teams=(teams[0], teams[1]),
        winner_side=d["winner_side"],
        probability=d["probability"],
        finish=d["finish"],
        rating=d["rating"],
        finisher=d["finisher"],
        scorer=d["scorer"],
        pinned=d["pinned"],
        participants=participants,
        heat=tuple(
            HeatChange(a=h["a"], b=h["b"], before=h["before"], after=h["after"])
            for h in d["heat"]
        ),
        injury=None if injury is None else _injury_in(injury),
        popularity_delta=d["popularity_delta"],
    )


def verify_matches(raw: dict[str, Any]) -> None:
    """`dump` 결과의 경기 기록을 **읽기와 같은 규칙으로** 본다. 어긋나면 `CorruptSaveError`.

    세계 전체를 되살리지 않고 기록만 본다 — 저장마다 도는 경로이고, 나머지 칸의 타입은
    이 함수의 책임이 아니다.
    """
    try:
        for record in raw["matches"]:
            _match_in(record)
        _since_in(raw["match_records_since"])
    except (KeyError, TypeError) as e:
        raise CorruptSaveError("세이브를 되살릴 수 없습니다") from e


def _since_in(value: Any) -> tuple[int, int] | None:
    """`match_records_since` — `null` 이거나 `[시즌, 주차]` 정수 둘. 그 밖은 손상."""
    if value is None:
        return None
    if (
        isinstance(value, list)
        and len(value) == 2
        and all(type(v) is int and v >= 1 for v in value)
    ):
        return (value[0], value[1])
    raise CorruptSaveError("세이브를 되살릴 수 없습니다")


def _wrestler_out(w: Wrestler) -> dict[str, Any]:
    return {
        "name": w.name,
        "style": w.style,
        "brand": w.brand,
        "age": w.age,
        "debut_age": w.debut_age,
        "alignment": str(w.alignment),
        "popularity": w.popularity,
        "ability": _ability_out(w.ability),
        "condition": w.condition,
        "status": str(w.status),
        "wins": w.wins,
        "losses": w.losses,
        "reigns": list(w.reigns),
        "held": list(w.held),
        "injuries": [_injury_out(i) for i in w.injuries],
        "out_weeks": w.out_weeks,
        "losing_streak": w.losing_streak,
        "win_streak": w.win_streak,
        "best_win_streak": w.best_win_streak,
        "streaks_since": (None if w.streaks_since is None else list(w.streaks_since)),
        "consecutive_matches": w.consecutive_matches,
        "trend": [
            {"season": t.season, "age": t.age, "ability": _ability_out(t.ability)}
            for t in w.trend
        ],
        "intent": (
            None
            if w.intent is None
            else {
                "origin": w.intent.origin,
                "cause": str(w.intent.cause),
                "season": w.intent.season,
                "week": w.intent.week,
                "final_season": w.intent.final_season,
            }
        ),
        "retirement": (
            None
            if w.retirement is None
            else {
                "cause": str(w.retirement.cause),
                "season": w.retirement.season,
                "week": w.retirement.week,
                "age": w.retirement.age,
                "wins": w.retirement.wins,
                "losses": w.retirement.losses,
                "held": list(w.retirement.held),
                "reigns": w.retirement.reigns,
                "titles": list(w.retirement.titles),
                "note": w.retirement.note,
            }
        ),
        "is_player": w.is_player,
    }


def _wrestler_in(d: dict[str, Any]) -> Wrestler:
    intent = d.get("intent")
    retirement = d.get("retirement")
    return Wrestler(
        name=d["name"],
        style=d["style"],
        brand=d["brand"],
        age=d["age"],
        debut_age=d["debut_age"],
        alignment=d["alignment"],
        popularity=d["popularity"],
        ability=_ability(d["ability"]),
        condition=d["condition"],
        status=d["status"],
        wins=d["wins"],
        losses=d["losses"],
        reigns=tuple(d.get("reigns", ())),
        held=tuple(d.get("held", ())),
        injuries=tuple(_injury_in(i) for i in d.get("injuries", ())),
        out_weeks=d.get("out_weeks", 0),
        losing_streak=d.get("losing_streak", 0),
        # **기본값으로 읽지 않는다.** 빠진 칸을 0 · `None` 으로 메우면 "데뷔부터 센
        # 정확한 값 0" 이 되어 버린다. v1 은 업그레이드가 채워 오므로 여기 닿을 때는
        # 항상 있다 — 없으면 세이브가 깨진 것이다.
        win_streak=d["win_streak"],
        best_win_streak=d["best_win_streak"],
        streaks_since=(
            None if d["streaks_since"] is None else tuple(d["streaks_since"])
        ),
        consecutive_matches=d.get("consecutive_matches", 0),
        trend=tuple(
            AbilitySnapshot(
                season=t["season"], age=t["age"], ability=_ability(t["ability"])
            )
            for t in d.get("trend", ())
        ),
        intent=(
            None
            if not intent
            else RetirementIntent(
                origin=intent["origin"],
                cause=intent["cause"],
                season=intent["season"],
                week=intent["week"],
                final_season=intent.get("final_season", False),
            )
        ),
        retirement=(
            None
            if not retirement
            else Retirement(
                cause=retirement["cause"],
                season=retirement["season"],
                week=retirement["week"],
                age=retirement["age"],
                wins=retirement["wins"],
                losses=retirement["losses"],
                held=tuple(retirement.get("held", ())),
                reigns=retirement.get("reigns", 0),
                titles=tuple(retirement.get("titles", ())),
                note=retirement.get("note", ""),
            )
        ),
        is_player=d.get("is_player", False),
    )


def dump(state: WorldState) -> dict[str, Any]:
    """세계를 JSON 으로 쓸 수 있는 dict 로. **`applied` 는 정렬해서 눕힌다.**

    `frozenset` 은 JSON 에 없고, 순서가 들쭉날쭉하면 같은 세계가 매번 다른
    바이트로 저장되어 diff 와 캐시가 쓸모없어진다.
    """
    return {
        "version": SCHEMA_VERSION,
        "seed": state.seed,
        "player": state.player,
        "season": state.season,
        "week": state.week,
        "phase": str(state.phase),
        "action_points": state.action_points,
        "roster": [_wrestler_out(w) for w in state.roster],
        "relationships": [
            {
                "a": r.a,
                "b": r.b,
                "kind": str(r.kind),
                "heat": r.heat,
                "started_week": r.started_week,
                "last_week": r.last_week,
                "history": list(r.history),
            }
            for r in state.relationships
        ],
        "titles": [
            {
                "name": t.name,
                "brand": t.brand,
                "required_popularity": t.required_popularity,
                "holder": t.holder,
                "defenses": t.defenses,
                "won_week": t.won_week,
            }
            for t in state.titles
        ],
        "pending": [
            {
                "id": e.id,
                "kind": e.kind,
                "season": e.season,
                "week": e.week,
                "subject": e.subject,
                "other": e.other,
                "headline": e.headline,
                "detail": e.detail,
                "choices": [
                    {
                        "code": c.code,
                        "label": c.label,
                        "enabled": c.enabled,
                        "note": c.note,
                    }
                    for c in e.choices
                ],
            }
            for e in state.pending
        ],
        "log": [
            {
                "season": e.season,
                "week": e.week,
                "kind": e.kind,
                "subject": e.subject,
                "summary": e.summary,
                "other": e.other,
                "result": e.result,
                "title": e.title,
            }
            for e in state.log
        ],
        "seasons": [
            {
                "season": s.season,
                "wins": s.wins,
                "losses": s.losses,
                "age": s.age,
                "ability": _ability_out(s.ability),
                "ability_delta": _ability_out(s.ability_delta),
                "titles_won": list(s.titles_won),
                "defenses": s.defenses,
                "injuries": s.injuries,
                "retired": list(s.retired),
                "highlights": list(s.highlights),
                "risk_band": s.risk_band,
            }
            for s in state.seasons
        ],
        "matches": [_match_out(m) for m in state.matches],
        "match_records_since": (
            None
            if state.match_records_since is None
            else list(state.match_records_since)
        ),
        "applied": sorted(state.applied),
    }


def load(raw: dict[str, Any]) -> WorldState:
    """dict 를 세계로. 되살릴 수 없으면 `CorruptSaveError`.

    **조용히 읽지 않는다.** 판본이 달라 칸이 비면 데이터클래스 기본값이 채우므로
    전적 0 · 벨트 없음인 세이브가 정상처럼 보인다. 그건 데이터 손실이 조용히
    일어나는 모양이라 막는다.

    **거부는 한 가지 이름으로 한다.** 판본 불일치와 칸 누락은 원인이 다르지만
    호출자에게는 같은 사실이다 — 저장된 세이브를 읽을 수 없다. 칸 누락이 날것의
    `KeyError` 로 올라가면 `LookupError` 하위라서 라우터의 404 분기에 걸리고,
    그 `KeyError` 의 인수(= 빠진 칸 이름)가 응답에 실린다. `CorruptSaveError`
    독스트링에 실측이 적혀 있다.
    """
    version = raw.get("version")
    # `type(...) is int` 를 먼저 본다 — 리스트 같은 값이 오면 `in` 이 `TypeError` 를
    # 내서 손상 세이브가 500 이 되고, `True` 는 `1` 과 같은 키로 잡혀 v1 처럼 읽힌다.
    if version != SCHEMA_VERSION and (
        type(version) is not int or version not in _UPGRADES
    ):
        raise CorruptSaveError(
            f"세이브 판본이 맞지 않습니다: {version} (이 서버는 {SCHEMA_VERSION})"
        )

    try:
        while raw["version"] != SCHEMA_VERSION:
            raw = _UPGRADES[raw["version"]](raw)
        return _world(raw)
    except (KeyError, TypeError) as e:
        # **무엇이 빠졌는지 메시지에 담지 않는다.** 저장된 JSON 의 칸 이름은
        # 내부 사정이고, 이 예외는 응답 본문으로 나가는 경로에 있다. 원인은
        # `raise … from e` 로 로그(스택)에만 남는다.
        raise CorruptSaveError("세이브를 되살릴 수 없습니다") from e


def _upgrade_v1_to_v2(raw: dict[str, Any]) -> dict[str, Any]:
    """v1 → v2. **옛 칸은 그대로 두고 선수마다 연승 칸 셋만 더한다.** 입력은 바꾸지 않는다.

    선수마다 셋 중 하나로 정한다:

    1. **경기가 없다**(`wins + losses == 0`) — 연승 0 · 최장 0 이 정확한 값이다.
    2. **플레이어이고 로그가 온전하다** — 남은 경기 로그를 처음부터 다시 센다.
       온전하다는 것은 둘 다 참일 때다:
         - 로그 첫 줄이 그 선수의 `debut` 다 (`MAX_LOG` 로 잘린 적이 없다)
         - 로그의 경기 수와 승수가 `wins` · `losses` 와 **정확히** 맞는다
       엔진은 플레이어 경기마다 `match` 로그를 한 줄 남기므로 둘이 맞으면 빠진
       경기가 없다.
    3. **그 밖** — 옛 경기를 다시 셀 수 없다. 0에서 시작하고 `streaks_since` 에
       세이브의 현재 `(시즌, 주차)` 를 적는다. NPC 는 경기가 있으면 항상 여기다 —
       NPC 경기는 로그에 이름이 남지만 태그전에서는 로그의 상대와 전적이 오른
       선수가 다를 수 있어(`_apply_outcome` 의 `foe_name`) 로그로 정확히 셀 수 없다.

    **추정하지 않는다.** `losing_streak > 0` 이면 현재 연승이 0인 것은 확실하지만
    최장 연승은 여전히 모르므로, 3번은 칸 셋을 함께 "여기부터" 로 둔다.
    """
    player = raw["player"]
    log = raw.get("log", ())
    intact = bool(log) and log[0]["kind"] == "debut" and log[0]["subject"] == player
    since = [raw["season"], raw["week"]]

    roster = []
    for w in raw.get("roster", ()):
        played = w["wins"] + w["losses"]
        current, best, origin = 0, 0, since
        if played == 0:
            origin = None
        elif w["name"] == player and intact:
            results = [
                e["result"] == "win"
                for e in log
                if e["kind"] == "match"
                and e["subject"] == player
                and e.get("result") in ("win", "loss")
            ]
            if len(results) == played and sum(results) == w["wins"]:
                current, best = tally.replay(results)
                origin = None
        roster.append(
            {
                **w,
                "win_streak": current,
                "best_win_streak": best,
                "streaks_since": origin,
            }
        )
    return {**raw, "version": 2, "roster": roster}


def _upgrade_v2_to_v3(raw: dict[str, Any]) -> dict[str, Any]:
    """v2 → v3. **옛 칸은 그대로 두고 경기 기록 칸 둘만 더한다.** 입력은 바꾸지 않는다.

    지난 경기를 기록으로 **백필하지 않는다** — 그 주의 인기도·컨디션·승률이 세이브에
    남아 있지 않아서, 만들면 추정이 된다. 대신 `match_records_since` 에 세이브의 현재
    `(시즌, 주차)`(= 다음에 치를 주차)를 적는다. 그 이전 경기는 "기록 도입 전" 이다.

    새 커리어는 이 칸이 `null` 이다 — 데뷔부터 기록한다. 업그레이드한 커리어와 새
    커리어가 그 한 칸으로 갈린다.
    """
    return {
        **raw,
        "version": 3,
        "matches": [],
        "match_records_since": [raw["season"], raw["week"]],
    }


#: 아는 옛 판본 → 한 단계 올리는 함수. `load` 가 현재 판본에 닿을 때까지 잇는다.
_UPGRADES = {1: _upgrade_v1_to_v2, 2: _upgrade_v2_to_v3}


def _world(raw: dict[str, Any]) -> WorldState:
    """`load` 의 본체. **따로 떼어 둔 것은 try 블록을 좁히려는 것이다** — 판본
    검사까지 감싸면 그쪽이 내는 `CorruptSaveError` 를 다시 감싸게 된다.
    """
    return WorldState(
        seed=raw["seed"],
        player=raw["player"],
        season=raw["season"],
        week=raw["week"],
        phase=raw["phase"],
        action_points=raw["action_points"],
        roster=tuple(_wrestler_in(w) for w in raw.get("roster", ())),
        relationships=tuple(
            Relationship(
                a=r["a"],
                b=r["b"],
                kind=r["kind"],
                heat=r["heat"],
                started_week=r["started_week"],
                last_week=r["last_week"],
                history=tuple(r.get("history", ())),
            )
            for r in raw.get("relationships", ())
        ),
        titles=tuple(
            Title(
                name=t["name"],
                brand=t["brand"],
                required_popularity=t["required_popularity"],
                holder=t.get("holder"),
                defenses=t.get("defenses", 0),
                won_week=t.get("won_week"),
            )
            for t in raw.get("titles", ())
        ),
        pending=tuple(
            PendingEvent(
                id=e["id"],
                kind=e["kind"],
                season=e["season"],
                week=e["week"],
                subject=e["subject"],
                other=e.get("other"),
                headline=e.get("headline", ""),
                detail=e.get("detail", ""),
                choices=tuple(
                    Choice(
                        code=c["code"],
                        label=c["label"],
                        enabled=c.get("enabled", True),
                        note=c.get("note", ""),
                    )
                    for c in e.get("choices", ())
                ),
            )
            for e in raw.get("pending", ())
        ),
        log=tuple(
            LogEntry(
                season=e["season"],
                week=e["week"],
                kind=e["kind"],
                subject=e["subject"],
                summary=e.get("summary", ""),
                other=e.get("other"),
                result=e.get("result"),
                title=e.get("title"),
            )
            for e in raw.get("log", ())
        ),
        seasons=tuple(
            SeasonSummary(
                season=s["season"],
                wins=s["wins"],
                losses=s["losses"],
                age=s["age"],
                ability=_ability(s["ability"]),
                ability_delta=_ability(s["ability_delta"]),
                titles_won=tuple(s.get("titles_won", ())),
                defenses=s.get("defenses", 0),
                injuries=s.get("injuries", 0),
                retired=tuple(s.get("retired", ())),
                highlights=tuple(s.get("highlights", ())),
                risk_band=s.get("risk_band", ""),
            )
            for s in raw.get("seasons", ())
        ),
        # **v3 칸은 기본값으로 읽지 않는다.** 빈 `matches` 와 `null` 은 "데뷔부터 기록했고
        # 경기가 없었다" 는 **정확한 사실**로 읽히므로, 빠진 칸을 그것으로 메우면 안 된다.
        # v2 이하는 업그레이드가 채워 오므로 여기 닿을 때는 항상 있다.
        matches=tuple(_match_in(m) for m in raw["matches"]),
        match_records_since=_since_in(raw["match_records_since"]),
        applied=frozenset(raw.get("applied", ())),
    )
