"""52주 시즌과 노화 (`career_season` · `career_aging`).

**붙드는 것은 계약이다.**

1. **시즌은 52주** — 40이 아니고, 숫자는 한 곳(`Balance.season_weeks`)에서 온다
2. **결산과 다음 시즌이 갈라져 있다** — 한 호출로 묶이지 않는다
3. **나이는 결산에서만, 한 번만 오른다** — 재시도가 두 살을 먹이지 않는다
4. **노화는 일괄 하락이 아니다** — 기술·마이크는 오르고 체력·회복력만 내린다
5. **시즌을 넘겨도 전부 보존된다** — 주차만 1로 돌아간다

순수 함수라 DB가 필요 없다.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from kayfabe.domain.services import career_engine as engine
from kayfabe.domain.services import career_season as season_rules
from kayfabe.domain.services.career_aging import age_one_season, recent_trend
from kayfabe.domain.services.career_world import (
    SEASON_WEEKS,
    Ability,
    Balance,
    Phase,
    RetirementCause,
    RetirementIntent,
    Status,
    Title,
)

BAL = Balance()


def _world(**kwargs):
    return engine.create_world(
        player="Tester", style="테크니션", seed=11, age=24, balance=BAL, **kwargs
    )


def _play_to_season_end(world, balance=BAL, limit=200):
    for _ in range(limit):
        if world.phase != Phase.IN_SEASON:
            return world
        world = engine.advance_week(world, balance=balance).state
    raise AssertionError("시즌이 끝나지 않았다")


# ── 1. 52주 ───────────────────────────────────────────────────────


def test_season_is_52_weeks_not_40():
    """**40주가 아니다.** 기본값이 52이고 상수가 한 곳에서 온다."""
    assert SEASON_WEEKS == 52
    assert Balance().season_weeks == 52


def test_season_length_is_configurable():
    """시즌 길이는 설정이다 — 짧은 시즌으로도 돌아간다(사용자 요구 §1 마지막 줄)."""
    short = Balance(season_weeks=6)
    world = _play_to_season_end(_world(), balance=short)
    assert world.week == short.season_weeks + 1
    assert world.phase == Phase.SETTLEMENT


def test_plays_all_52_weeks_then_enters_settlement():
    """1주차부터 52주차까지 진행하고 결산 단계로 넘어간다."""
    world = _play_to_season_end(_world())
    assert world.week == 53
    assert world.season == 1
    assert world.phase == Phase.SETTLEMENT


def test_week_advance_blocked_after_52():
    """52주를 쓴 뒤에는 주차 진행이 **막힌다** — 결산이 먼저다."""
    world = _play_to_season_end(_world())
    with pytest.raises(ValueError, match="결산이 먼저"):
        engine.advance_week(world, balance=BAL)


# ── 2 · 3. 결산 · 나이 ────────────────────────────────────────────


def test_settle_then_next_season_resets_week_to_one():
    """결산 → 다음 시즌. **주차가 1로 돌아가고 시즌 번호가 오른다.**"""
    world = season_rules.settle(_play_to_season_end(_world()), balance=BAL)
    assert world.phase == Phase.OFFSEASON
    nxt = season_rules.start_next_season(world, balance=BAL)
    assert (nxt.season, nxt.week, nxt.phase) == (2, 1, Phase.IN_SEASON)


def test_settle_raises_before_season_is_over():
    """시즌 중에는 결산할 수 없다."""
    with pytest.raises(ValueError, match="결산할 단계가 아닙니다"):
        season_rules.settle(_world(), balance=BAL)


def test_next_season_raises_before_settlement():
    """결산을 건너뛰고 다음 시즌으로 갈 수 없다 — 그러면 기록이 남지 않는다."""
    world = _play_to_season_end(_world())
    with pytest.raises(ValueError, match="단계가 아닙니다"):
        season_rules.start_next_season(world, balance=BAL)


def test_age_increases_exactly_once_per_season():
    """**나이가 시즌당 한 살만 오른다.** 52주가 1년이다."""
    world = _world()
    start_age = world.hero.age
    world = season_rules.settle(_play_to_season_end(world), balance=BAL)
    assert world.hero.age == start_age + 1


def test_settle_is_idempotent_age_does_not_double():
    """결산을 두 번 불러도 **나이가 두 번 오르지 않는다**(사용자 요구 §2).

    이것이 멱등 키의 존재 이유다. 결산이 재시도되는 경로는 흔하다 — 네트워크
    재전송·버튼 두 번 누르기.
    """
    world = _play_to_season_end(_world())
    once = season_rules.settle(world, balance=BAL)
    twice = season_rules.settle(once, balance=BAL)
    thrice = season_rules.settle(twice, balance=BAL)
    assert once.hero.age == twice.hero.age == thrice.hero.age
    assert len(once.seasons) == len(twice.seasons) == len(thrice.seasons) == 1


def test_start_next_season_is_idempotent():
    """다음 시즌 시작도 멱등이다 — 두 번 불러도 시즌이 둘 오르지 않는다."""
    world = season_rules.settle(_play_to_season_end(_world()), balance=BAL)
    once = season_rules.start_next_season(world, balance=BAL)
    twice = season_rules.start_next_season(once, balance=BAL)
    assert (once.season, once.week) == (twice.season, twice.week) == (2, 1)


def test_season_summary_records_age_before_aging():
    """결산표의 나이는 **늙기 전** 값이다(§6 "시즌 종료 당시 선수 나이")."""
    world = _play_to_season_end(_world())
    age_at_end = world.hero.age
    settled = season_rules.settle(world, balance=BAL)
    assert settled.seasons[-1].age == age_at_end
    assert settled.hero.age == age_at_end + 1


# ── 4. 노화는 일괄 하락이 아니다 ──────────────────────────────────


def test_aging_raises_skill_and_lowers_body():
    """**일괄 하락이 아니다** — 기술·마이크는 오르고 체력·회복력만 내린다."""
    world = _world()
    veteran = replace(
        world.hero,
        age=38,
        ability=Ability(in_ring=70, mic=65, stamina=70, resilience=68),
    )
    older = age_one_season(veteran, seed=1, balance=BAL, season=1)
    assert older.age == 39
    assert older.ability.in_ring >= veteran.ability.in_ring
    assert older.ability.mic > veteran.ability.mic
    assert older.ability.stamina < veteran.ability.stamina
    assert older.ability.resilience < veteran.ability.resilience


def test_young_wrestler_does_not_decay():
    """`decline_age` 이전에는 몸이 깎이지 않는다."""
    world = _world()
    young = replace(world.hero, age=25, ability=Ability(50, 50, 80, 80))
    older = age_one_season(young, seed=1, balance=BAL, season=1)
    assert older.ability.stamina == 80
    assert older.ability.resilience == 80
    assert older.ability.in_ring > 50


def test_resilience_falls_faster_than_stamina():
    """회복이 먼저 늦어진다 — 그 순서가 은퇴 위험의 모양을 만든다."""
    world = _world()
    old = replace(world.hero, age=42, ability=Ability(80, 75, 60, 60))
    older = age_one_season(old, seed=5, balance=BAL, season=1)
    lost_stamina = 60 - older.ability.stamina
    lost_resilience = 60 - older.ability.resilience
    assert lost_resilience > lost_stamina


def test_recent_trend_needs_two_seasons():
    """추이는 스냅샷 둘이 있어야 난다 — 하나면 `None`."""
    world = _world()
    assert recent_trend(world.hero) is None


# ── 5. 보존 ───────────────────────────────────────────────────────


def test_next_season_preserves_everything_but_week():
    """**시즌을 넘겨도 전부 남는다** — 전적·능력치·관계·타이틀·부상·기록."""
    world = _play_to_season_end(_world())
    before = world.hero
    settled = season_rules.settle(world, balance=BAL)
    nxt = season_rules.start_next_season(settled, balance=BAL)
    after = nxt.hero

    assert after.wins == before.wins
    assert after.losses == before.losses
    assert after.reigns == before.reigns
    assert after.held == before.held
    assert len(after.injuries) == len(before.injuries)
    assert after.debut_age == before.debut_age
    # 기록과 관계는 누적된다.
    assert len(nxt.log) >= len(world.log)
    assert len(nxt.relationships) == len(world.relationships)
    assert len(nxt.seasons) == 1


def test_season_summary_accumulates_across_seasons():
    """시즌 결산표가 시즌마다 한 장씩 쌓인다."""
    world = _world()
    for expected in (1, 2):
        world = season_rules.settle(_play_to_season_end(world), balance=BAL)
        assert len(world.seasons) == expected
        assert world.seasons[-1].season == expected
        if expected == 1:
            world = season_rules.start_next_season(world, balance=BAL)


def test_season_stats_are_per_season_not_cumulative():
    """결산의 승패는 **그 시즌 것**이고, 선수의 전적은 통산이다."""
    world = season_rules.settle(_play_to_season_end(_world()), balance=BAL)
    s1 = world.seasons[-1]
    world = season_rules.start_next_season(world, balance=BAL)
    world = season_rules.settle(_play_to_season_end(world), balance=BAL)
    s2 = world.seasons[-1]
    assert s1.wins + s2.wins == world.hero.wins
    assert s1.losses + s2.losses == world.hero.losses


def test_ability_delta_is_not_always_zero():
    """결산이 능력치 변화를 **실제로** 센다.

    첫 판본은 시즌 시작 스냅샷을 결산에서 찍고 같은 값과 비교해 변화량이 항상
    0이었다. 스냅샷을 시즌 시작으로 옮겨 고쳤고, 이 테스트가 그 회귀를 막는다.
    """
    world = season_rules.settle(_play_to_season_end(_world()), balance=BAL)
    delta = world.seasons[-1].ability_delta
    assert (delta.in_ring, delta.mic, delta.stamina, delta.resilience) != (0, 0, 0, 0)


# ── 타이틀 공석 ───────────────────────────────────────────────────


def test_vacating_titles_is_idempotent():
    """벨트 공석 처리가 멱등이다 — 같은 은퇴가 두 번 처리되어도 한 번만 비운다."""
    world = _world()
    world = replace(
        world,
        titles=(
            Title(
                name="NXT Championship",
                brand="NXT",
                required_popularity=40,
                holder="Tester",
                defenses=3,
            ),
        ),
    )
    once = season_rules.vacate_titles_of(world, "Tester", reason="은퇴")
    twice = season_rules.vacate_titles_of(once, "Tester", reason="은퇴")
    assert once.titles[0].holder is None
    assert once.titles[0].defenses == 0
    assert len(twice.log) == len(once.log)


def test_retired_champion_belt_becomes_vacant_at_settlement():
    """은퇴한 챔피언의 벨트가 공석이 된다(§3.4)."""
    world = _play_to_season_end(_world())
    hero = world.hero
    world = replace(
        world,
        roster=tuple(
            replace(
                w,
                intent=None,
                status=Status.ACTIVE,
            )
            if w.name != hero.name
            else replace(
                w,
                held=("NXT Championship",),
                intent=RetirementIntent(
                    origin="self",
                    cause=RetirementCause.VOLUNTARY,
                    season=1,
                    week=50,
                    final_season=True,
                ),
            )
            for w in world.roster
        ),
        titles=(
            Title(
                name="NXT Championship",
                brand="NXT",
                required_popularity=40,
                holder=hero.name,
                defenses=2,
            ),
        ),
    )
    settled = season_rules.settle(world, balance=BAL)
    assert settled.hero.status == Status.RETIRED
    assert settled.titles[0].holder is None
    # **기록은 남는다** — 은퇴 당시 들고 있던 벨트가 보존된다.
    assert settled.hero.retirement is not None
    assert "NXT Championship" in settled.hero.retirement.held
