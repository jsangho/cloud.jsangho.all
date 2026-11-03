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

아래 상한은 실측보다 넉넉하게 잡은 **회귀 경보**다. 넘으면 무엇이 커졌는지 보고
상한 정책을 다시 정한다 — 숫자만 올리지 않는다.
"""

from __future__ import annotations

import json
from dataclasses import replace

from kayfabe.adapter.outbound.pg.career_world_codec import dump
from kayfabe.domain.services import career_engine as engine
from kayfabe.domain.services import career_events as events
from kayfabe.domain.services import career_season as season_rules
from kayfabe.domain.services.career_world import Balance, Phase, WorldState

ROSTER_SIZE = 102
SEED = 7

#: 시작 세이브 상한(바이트). 실측 61,862.
START_LIMIT = 70_000
#: 시즌당 증가 상한(바이트). 실측 최대 42,723.
GROWTH_LIMIT = 55_000


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


def test_v2_fields_cost_is_small() -> None:
    """v2 가 더한 칸 셋의 비용 — 선수당 100 B 미만."""
    world = _world()
    raw = dump(world)
    for w in raw["roster"]:
        for key in ("win_streak", "best_win_streak", "streaks_since"):
            del w[key]
    stripped = len(json.dumps(raw, ensure_ascii=False).encode("utf-8"))

    assert (_size(world) - stripped) / ROSTER_SIZE < 100
