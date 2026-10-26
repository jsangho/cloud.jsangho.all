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
from kayfabe.domain.services.career_world import (
    Ability,
    AbilitySnapshot,
    Choice,
    Injury,
    LogEntry,
    PendingEvent,
    Relationship,
    Retirement,
    RetirementIntent,
    SeasonSummary,
    Title,
    WorldState,
    Wrestler,
)

#: 세이브 모양의 판본. 칸을 더하기만 할 때는 올리지 않아도 된다(없는 칸은
#: 데이터클래스 기본값이 채운다). **칸의 뜻이 바뀌면** 올린다.
SCHEMA_VERSION = 1


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
        "injuries": [
            {
                "kind": i.kind,
                "severity": str(i.severity),
                "season": i.season,
                "week": i.week,
                "weeks_out": i.weeks_out,
                "recovered": i.recovered,
                "recurrence": i.recurrence,
                "permanent": i.permanent,
            }
            for i in w.injuries
        ],
        "out_weeks": w.out_weeks,
        "losing_streak": w.losing_streak,
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
        injuries=tuple(
            Injury(
                kind=i["kind"],
                severity=i["severity"],
                season=i["season"],
                week=i["week"],
                weeks_out=i["weeks_out"],
                recovered=i.get("recovered", False),
                recurrence=i.get("recurrence", False),
                permanent=i.get("permanent", False),
            )
            for i in d.get("injuries", ())
        ),
        out_weeks=d.get("out_weeks", 0),
        losing_streak=d.get("losing_streak", 0),
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
    if version != SCHEMA_VERSION:
        raise CorruptSaveError(
            f"세이브 판본이 맞지 않습니다: {version} (이 서버는 {SCHEMA_VERSION})"
        )

    try:
        return _world(raw)
    except (KeyError, TypeError) as e:
        # **무엇이 빠졌는지 메시지에 담지 않는다.** 저장된 JSON 의 칸 이름은
        # 내부 사정이고, 이 예외는 응답 본문으로 나가는 경로에 있다. 원인은
        # `raise … from e` 로 로그(스택)에만 남는다.
        raise CorruptSaveError("세이브를 되살릴 수 없습니다") from e


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
        applied=frozenset(raw.get("applied", ())),
    )
