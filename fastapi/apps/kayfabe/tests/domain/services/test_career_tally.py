"""커리어 카운터 — 총 경기 수 · 현재 연승 · 최장 연승.

**기준은 경기 로그다.** 엔진은 플레이어 경기마다 `match` 로그를 한 줄 쓰므로, 로그를
처음부터 다시 센 값과 엔진이 경기마다 올린 값이 같아야 한다.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from kayfabe.domain.services import career_engine as engine
from kayfabe.domain.services import career_events as events
from kayfabe.domain.services import career_tally as tally
from kayfabe.domain.services.career_world import Balance, Phase, WorldState


@pytest.mark.parametrize(
    ("results", "expected"),
    [
        ([], (0, 0)),
        ([False, False], (0, 0)),
        ([True], (1, 1)),
        ([True, True, False, True], (1, 2)),
        ([True, True, True, False, False], (0, 3)),
        ([False, True, True, False, True, True, True], (3, 3)),
    ],
)
def test_replay(results: list[bool], expected: tuple[int, int]) -> None:
    assert tally.replay(results) == expected


def test_step_never_lowers_best() -> None:
    assert tally.step(current=4, best=7, won=False) == (0, 7)
    assert tally.step(current=7, best=7, won=True) == (8, 8)


def _season(seed: int) -> WorldState:
    """한 시즌. 사건은 은퇴가 아닌 첫 선택지로 해결한다."""
    bal = Balance()
    world = engine.create_world(player="Tally", style="파워", seed=seed)
    for _ in range(bal.season_weeks):
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
        if world.phase != Phase.IN_SEASON:
            break
    return world


def _log_results(world: WorldState) -> list[bool]:
    return [
        e.result == "win"
        for e in world.log
        if e.kind == "match" and e.subject == world.player
    ]


@pytest.mark.parametrize("seed", range(1, 31))
def test_player_counters_equal_log_recount(seed: int) -> None:
    """서른 시즌. 엔진이 센 값 = 로그를 다시 센 값. 총 경기 수 = 로그의 경기 줄 수."""
    world = _season(seed)
    hero = world.hero
    results = _log_results(world)

    assert hero.streaks_since is None
    assert hero.match_count == len(results)
    assert hero.wins == sum(results)
    assert (hero.win_streak, hero.best_win_streak) == tally.replay(results)


@pytest.mark.parametrize("seed", range(1, 31))
def test_counter_invariants_hold_for_everyone(seed: int) -> None:
    """NPC 까지 — 현재 ≤ 최장 · 연승과 연패가 동시에 양수일 수 없다."""
    for w in _season(seed).roster:
        assert 0 <= w.win_streak <= w.best_win_streak
        assert w.best_win_streak <= w.wins
        assert not (w.win_streak > 0 and w.losing_streak > 0), w.name
        assert w.match_count == w.wins + w.losses


def test_counters_do_not_move_on_duplicate_week() -> None:
    """같은 주차를 두 번 적용해도 카운터가 두 번 오르지 않는다(`applied` 가 막는다)."""
    bal = Balance()
    world = engine.create_world(player="Tally", style="파워", seed=11)
    for _ in range(5):
        world = engine.advance_week(world, balance=bal).state
    # 주차를 되돌려 같은 키로 다시 들어온 상황(저장 실패 후 같은 상태로 재진입).
    rewound = replace(world, week=world.week - 1)

    again = engine.advance_week(rewound, balance=bal).state

    assert again.hero == rewound.hero
