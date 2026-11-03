"""세이브 크기. **진행 한 번이 JSONB 한 칸을 통째로 다시 쓴다** — 그래서 크기가 비용이다.

102명 세계(실제 남자부 명부와 같은 인원 — 이름·수치는 기본 NPC 를 복제한 가상 값)로
세 시즌을 돌려 시작 · 1 · 2 · 3시즌 끝의 크기를 잰다.

## 실측 (2026-11-03 · v2 · 시드 7)

    시작     61,862 B
    1시즌    87,544 B   (+25.7 KB)  로그 108줄 · 관계 24 · applied 103
    2시즌   128,879 B   (+41.3 KB)  로그 252줄 · 관계 50 · applied 239
    3시즌   171,602 B   (+42.7 KB)  로그 389줄 · 관계 94 · applied 374

증가분의 대부분은 **로그**(시즌당 약 25 KB, `MAX_LOG=1200` 에서 멈춘다)와 선수별
능력치 추이(`trend`, 12칸에서 멈춘다)다. **`applied` 는 상한이 없다**(시즌당 약
2.6 KB) — 정리는 이 단계에서 하지 않는다.

## v3 실측 (2026-11-03 · 경기 기록 추가 · 같은 시드)

    시작      61,906 B                기록   0건
    1시즌    106,217 B   (+44.3 KB)   기록  24건 · 18,631 B
    2시즌    166,880 B   (+60.7 KB)   기록  49건 · 37,959 B
    3시즌    230,745 B   (+63.9 KB)   기록  76건 · 59,101 B
    4시즌    288,433 B   (+57.7 KB)   기록  99건 · 77,571 B
    5시즌    325,174 B   (+36.7 KB)   기록 104건 · 81,542 B  ← 상한. 더 자라지 않는다

기록을 뺀 크기는 v2 와 같다(칸 둘의 이름 값 약 40 B). 기록 한 건은 싱글 평균
0.78 KB · 최대 0.97 KB, 태그 평균 1.14 KB · 최대 1.27 KB(골든 시드 11 의 태그
18건). 그래서 104건은 싱글만이면 약 82 KB, 전부 태그여도 약 115 KB 다.

시즌당 증가 상한을 55 KB → 75 KB 로 올린 근거가 위 표다(실측 최대 63.9 KB). 기록
구역은 따로 `104 × 1,300 B` 로 묶는다.

아래 상한은 실측보다 넉넉하게 잡은 **회귀 경보**다. 넘으면 무엇이 커졌는지 보고
상한 정책을 다시 정한다 — 숫자만 올리지 않는다.
"""

from __future__ import annotations

import json
from dataclasses import replace

from kayfabe.adapter.outbound.pg.career_world_codec import dump
from kayfabe.domain.services import career_engine as engine
from kayfabe.domain.services import career_events as events
from kayfabe.domain.services import career_match_record as records_mod
from kayfabe.domain.services import career_season as season_rules
from kayfabe.domain.services.career_world import Balance, Phase, WorldState

ROSTER_SIZE = 102
SEED = 7

#: 시작 세이브 상한(바이트). 실측 61,862.
START_LIMIT = 70_000
#: 시즌당 증가 상한(바이트). v2 실측 최대 42,723 → v3(경기 기록) 실측 최대 63,865.
GROWTH_LIMIT = 75_000
#: 경기 기록 한 건의 상한(바이트). 실측 최대 — 싱글 973 · 태그 1,265.
RECORD_LIMIT = 1_300


def _size(world: WorldState) -> int:
    return len(json.dumps(dump(world), ensure_ascii=False).encode("utf-8"))


def _world() -> WorldState:
    base = engine.default_roster()
    roster = tuple(
        replace(
            base[i % len(base)],
            name=f"W{i:03d}",
            brand=("NXT", "Raw", "SmackDown")[i % 3],
        )
        for i in range(ROSTER_SIZE)
    )
    return engine.create_world(player="Hero", style="파워", seed=SEED, roster=roster)


def _play_season(world: WorldState, bal: Balance) -> WorldState:
    for _ in range(bal.season_weeks):
        if world.phase != Phase.IN_SEASON:
            break
        for event in list(world.pending):
            code = next(
                (c.code for c in event.choices if c.enabled and c.code != "retire"),
                None,
            )
            if code:
                world = events.resolve(
                    world, event_id_=event.id, choice_code=code, balance=bal
                )
        world = engine.advance_week(world, balance=bal).state
    return season_rules.settle(world, balance=bal)


def measure() -> list[int]:
    """시작 · 1 · 2 · 3시즌 끝(결산 직후)의 크기."""
    bal = Balance()
    world = _world()
    sizes = [_size(world)]
    for _ in range(3):
        world = _play_season(world, bal)
        sizes.append(_size(world))
        assert world.phase == Phase.OFFSEASON, "플레이어가 은퇴하면 측정이 짧아진다"
        world = season_rules.start_next_season(world, balance=bal)
    return sizes


def test_save_size_stays_within_budget() -> None:
    sizes = measure()

    assert sizes[0] < START_LIMIT
    growth = [b - a for a, b in zip(sizes, sizes[1:], strict=False)]
    assert all(0 < g < GROWTH_LIMIT for g in growth), growth


def test_match_records_stop_growing_at_the_cap() -> None:
    """다섯 시즌 — 기록이 104건에서 멈추고, 기록 구역이 `104 × RECORD_LIMIT` 안이다."""
    bal = Balance()
    world = _world()
    for _ in range(5):
        world = _play_season(world, bal)
        world = season_rules.start_next_season(world, balance=bal)
    raw = dump(world)
    records = raw["matches"]

    assert len(records) == records_mod.MAX_MATCH_RECORDS
    assert all(_bytes(r) < RECORD_LIMIT for r in records)
    assert _bytes(records) < records_mod.MAX_MATCH_RECORDS * RECORD_LIMIT


def _bytes(value: object) -> int:
    return len(json.dumps(value, ensure_ascii=False).encode("utf-8"))


def test_v2_fields_cost_is_small() -> None:
    """v2 가 더한 칸 셋의 비용 — 선수당 100 B 미만."""
    world = _world()
    raw = dump(world)
    for w in raw["roster"]:
        for key in ("win_streak", "best_win_streak", "streaks_since"):
            del w[key]
    stripped = len(json.dumps(raw, ensure_ascii=False).encode("utf-8"))

    assert (_size(world) - stripped) / ROSTER_SIZE < 100
