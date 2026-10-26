"""세이브 왕복. **칸이 하나 새면 그 세이브는 조용히 망가진다.**

세계를 JSON 한 칸에 통째로 넣기로 한 대가가 여기 있다 — 스키마가 칸을 세어 주지
않으므로 도메인에 필드를 더하고 코덱을 안 고치면 **아무 에러 없이** 그 값이 저장에서
사라진다. 다음 `load` 는 데이터클래스 기본값으로 칸을 채우고, 전적 0 · 벨트 없음인
세이브가 정상처럼 읽힌다.

그래서 이 파일은 두 가지를 본다:

1. **왕복 동일성** — `load(dump(w)) == w`. 값이 오가며 변형되지 않는다.
2. **칸 수 대조** — 도메인 데이터클래스의 모든 필드가 dump 에 실제로 나타난다.
   새 필드를 더하고 코덱을 잊으면 이 테스트가 먼저 깨진다.

입력은 **최대로 채운 세계** 하나다. 주차를 돌려서 만든 세계를 쓰면 그날의 주사위에
따라 부상·사건·은퇴 칸이 비어 있을 수 있고, 비어 있는 칸은 왕복을 통과한다 —
아무것도 검증하지 않으면서.
"""

from __future__ import annotations

import json
from dataclasses import fields
from typing import Any

import pytest

from kayfabe.adapter.outbound.pg.career_world_codec import (
    SCHEMA_VERSION,
    dump,
    load,
)
from kayfabe.domain.services.career_world import (
    Ability,
    AbilitySnapshot,
    Alignment,
    Choice,
    Injury,
    LogEntry,
    PendingEvent,
    Phase,
    RelationKind,
    Relationship,
    Retirement,
    RetirementCause,
    RetirementIntent,
    SeasonSummary,
    Severity,
    Status,
    Title,
    WorldState,
    Wrestler,
)


def _maximal_world() -> WorldState:
    """**모든 칸이 비어 있지 않은 세계.** 선택적 칸까지 전부 채운다."""
    hero = Wrestler(
        name="Ho",
        style="하이플라이어",
        brand="Raw",
        age=34,
        debut_age=24,
        alignment=Alignment.HEEL,
        popularity=88,
        ability=Ability(in_ring=81, mic=66, stamina=58, resilience=54),
        condition=61,
        status=Status.RETIREMENT_PENDING,
        wins=73,
        losses=41,
        reigns=("NXT Championship", "World Heavyweight Championship"),
        held=("World Heavyweight Championship",),
        injuries=(
            Injury(
                kind="무릎",
                severity=Severity.MINOR,
                season=2,
                week=7,
                weeks_out=2,
                recovered=True,
            ),
            Injury(
                kind="무릎",
                severity=Severity.CAREER_THREATENING,
                season=9,
                week=31,
                weeks_out=24,
                recovered=False,
                recurrence=True,
                permanent=True,
            ),
        ),
        out_weeks=11,
        losing_streak=3,
        consecutive_matches=6,
        trend=(
            AbilitySnapshot(season=8, age=33, ability=Ability(80, 64, 62, 58)),
            AbilitySnapshot(season=9, age=34, ability=Ability(81, 66, 58, 54)),
        ),
        intent=RetirementIntent(
            origin="offered",
            cause=RetirementCause.REPEATED_INJURY,
            season=9,
            week=31,
            final_season=True,
        ),
        # **확정과 의사를 동시에 채운다.** 둘이 다른 칸임을 왕복이 지켜야 한다.
        retirement=Retirement(
            cause=RetirementCause.SEVERE_INJURY,
            season=9,
            week=33,
            age=34,
            wins=73,
            losses=41,
            held=("World Heavyweight Championship",),
            reigns=2,
            titles=("NXT Championship", "World Heavyweight Championship"),
            note="무릎 부상 재발",
        ),
        is_player=True,
    )
    npc = Wrestler(name="Dex Harlow", style="파워", brand="Raw", age=29)

    return WorldState(
        seed=4242,
        player=hero.name,
        season=9,
        week=33,
        phase=Phase.SETTLEMENT,
        action_points=1,
        roster=(hero, npc),
        relationships=(
            Relationship(
                a=hero.name,
                b=npc.name,
                kind=RelationKind.RIVAL,
                heat=-64,
                started_week=12,
                last_week=31,
                history=("ally→rival", "배신"),
            ),
        ),
        titles=(
            Title(
                name="World Heavyweight Championship",
                brand="Raw",
                required_popularity=85,
                holder=hero.name,
                defenses=4,
                won_week=401,
            ),
            # 공석도 함께 넣는다 — `holder=None` 이 왕복에서 빈 문자열이 되면 안 된다.
            Title(name="NXT Championship", brand="NXT", required_popularity=45),
        ),
        pending=(
            PendingEvent(
                id="evt:s9w31:medical:Ho",
                kind="medical",
                season=9,
                week=31,
                subject=hero.name,
                other=npc.name,
                headline="의료진이 복귀를 반대한다",
                detail="무릎이 같은 자리로 세 번째다.",
                choices=(
                    Choice(code="retire", label="은퇴한다", note="기록이 보존된다"),
                    Choice(
                        code="return",
                        label="복귀한다",
                        enabled=False,
                        note="영구 불가 판정이라 고를 수 없다",
                    ),
                ),
            ),
        ),
        log=(
            LogEntry(
                season=9,
                week=31,
                kind="match",
                subject=hero.name,
                summary="타이틀 방어 성공",
                other=npc.name,
                result="win",
                title="World Heavyweight Championship",
            ),
        ),
        seasons=(
            SeasonSummary(
                season=8,
                wins=21,
                losses=9,
                age=33,
                ability=Ability(80, 64, 62, 58),
                ability_delta=Ability(2, 3, -4, -5),
                titles_won=("World Heavyweight Championship",),
                defenses=3,
                injuries=1,
                retired=("Silas Grimm",),
                highlights=("월드 챔피언에 올랐다",),
                risk_band="주의",
            ),
        ),
        applied=frozenset({"week:s9w31", "settle:s8", "action:s9w31:0"}),
    )


def test_round_trip_preserves_every_value() -> None:
    world = _maximal_world()

    assert load(dump(world)) == world


def test_dump_is_stable_and_json_serializable() -> None:
    """같은 세계는 **같은 바이트**로 저장된다.

    `applied` 가 `frozenset` 이라 정렬하지 않으면 매번 순서가 달라지고, 그러면
    세이브 diff 가 쓸모없어진다(코덱 `dump` 가 적어 둔 약속이다).
    """
    world = _maximal_world()

    first = json.dumps(dump(world), ensure_ascii=False, sort_keys=False)
    second = json.dumps(dump(load(dump(world))), ensure_ascii=False, sort_keys=False)

    assert first == second


def test_unknown_version_is_refused() -> None:
    raw = dump(_maximal_world())
    raw["version"] = SCHEMA_VERSION + 1

    with pytest.raises(ValueError, match="세이브 판본"):
        load(raw)


def test_missing_version_is_refused() -> None:
    """판본 칸이 없는 세이브도 거부한다 — 옛 세이브를 기본값으로 메우지 않는다."""
    raw = dump(_maximal_world())
    del raw["version"]

    with pytest.raises(ValueError, match="세이브 판본"):
        load(raw)


# ── 칸 수 대조 ────────────────────────────────────────────────────


def _assert_covers(kind: type, payload: dict[str, Any]) -> None:
    missing = {f.name for f in fields(kind)} - set(payload)
    assert not missing, f"{kind.__name__} 의 칸이 dump 에서 빠졌다: {sorted(missing)}"


def test_dump_covers_every_dataclass_field() -> None:
    """**드리프트 감시.** 도메인에 칸을 더하고 코덱을 잊으면 여기서 걸린다.

    세이브는 JSON 한 칸이라 DB 스키마가 칸을 세어 주지 않는다. 이 테스트가 그
    역할을 대신한다.
    """
    raw = dump(_maximal_world())

    _assert_covers(WorldState, raw)

    hero = raw["roster"][0]
    _assert_covers(Wrestler, hero)
    _assert_covers(Ability, hero["ability"])
    _assert_covers(Injury, hero["injuries"][0])
    _assert_covers(AbilitySnapshot, hero["trend"][0])
    _assert_covers(RetirementIntent, hero["intent"])
    _assert_covers(Retirement, hero["retirement"])

    _assert_covers(Relationship, raw["relationships"][0])
    _assert_covers(Title, raw["titles"][0])
    _assert_covers(PendingEvent, raw["pending"][0])
    _assert_covers(Choice, raw["pending"][0]["choices"][0])
    _assert_covers(LogEntry, raw["log"][0])
    _assert_covers(SeasonSummary, raw["seasons"][0])
