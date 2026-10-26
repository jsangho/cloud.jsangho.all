"""커리어 엔진 · 경기 · 대진 (`career_engine` · `career_match`).

**붙드는 것은 계약이다.**

1. **결정론** — 같은 시드·같은 상태면 같은 결과
2. **주차 멱등** — 같은 주차를 두 번 진행할 수 없다
3. **대진에서 은퇴·부상자가 빠진다**
4. **전적과 경기 수가 맞는다** — 승+패 = 경기 수
5. **타이틀 변경과 재위 기록이 일관된다** — 방어는 재위를 늘리지 않는다
6. **인기도가 혼자 승패를 정하지 않는다** — 능력치가 따로 있다

순수 함수라 DB가 필요 없다.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from kayfabe.domain.services import career_engine as engine
from kayfabe.domain.services import career_season as season_rules
from kayfabe.domain.services.career_match import (
    simulate_single,
    simulate_tag,
    win_probability,
)
from kayfabe.domain.services.career_retirement import confirm
from kayfabe.domain.services.career_world import (
    Ability,
    Balance,
    Phase,
    RetirementCause,
    Status,
    Title,
    Wrestler,
)

BAL = Balance()


def _world(seed=5, style="파워", age=24):
    return engine.create_world(
        player="Hero", style=style, seed=seed, age=age, balance=BAL
    )


def _fighter(name, **kwargs) -> Wrestler:
    base = {
        "name": name,
        "style": "테크니션",
        "age": 28,
        "debut_age": 25,
        "ability": Ability(in_ring=60, mic=50, stamina=75, resilience=75),
        "popularity": 50,
        "condition": 80,
    }
    base.update(kwargs)
    return Wrestler(**base)


# ── 생성 ──────────────────────────────────────────────────────────


def test_create_world_starts_in_nxt_week_one():
    world = _world()
    assert (world.season, world.week, world.phase) == (1, 1, Phase.IN_SEASON)
    assert world.hero.brand == "NXT"
    assert world.hero.is_player
    assert world.hero.age == world.hero.debut_age
    assert world.action_points == BAL.action_points


def test_create_world_rejects_blank_name_and_bad_age():
    with pytest.raises(ValueError, match="링네임"):
        engine.create_world(player="  ", style="파워", seed=1)
    with pytest.raises(ValueError, match="데뷔 나이"):
        engine.create_world(player="X", style="파워", seed=1, age=12)
    with pytest.raises(ValueError, match="데뷔 나이"):
        engine.create_world(player="X", style="파워", seed=1, age=60)


def test_debut_age_never_changes():
    """커리어 시작 시 나이는 고정이다(§2)."""
    world = _world(age=27)
    for _ in range(5):
        world = engine.advance_week(world, balance=BAL).state
    world = season_rules.settle(
        replace(world, week=BAL.season_weeks + 1, phase=Phase.SETTLEMENT), balance=BAL
    )
    assert world.hero.debut_age == 27
    assert world.hero.age == 28


# ── 1. 결정론 ─────────────────────────────────────────────────────


def test_same_seed_same_outcome():
    """**같은 시드면 같은 커리어다**(§P0 경기 — 시드 재현)."""
    a = _world(seed=99)
    b = _world(seed=99)
    for _ in range(12):
        a = engine.advance_week(a, balance=BAL).state
        b = engine.advance_week(b, balance=BAL).state
    assert a == b


def test_different_seed_diverges():
    """시드가 다르면 갈린다 — 고정값이 아니라 시드 함수라는 뜻이다."""
    a, b = _world(seed=1), _world(seed=2)
    for _ in range(20):
        a = engine.advance_week(a, balance=BAL).state
        b = engine.advance_week(b, balance=BAL).state
    assert (a.hero.wins, a.hero.losses) != (
        b.hero.wins,
        b.hero.losses,
    ) or a.hero.popularity != b.hero.popularity


def test_match_result_is_order_independent():
    """인수 순서를 바꿔도 승자가 같다.

    `roll < p` 로 바로 비교하면 확률이 대칭인데 부등호가 비대칭이라 승자가
    뒤집힌다 — `match_sim` 이 실측으로 잡아 둔 함정이고 여기도 같다.
    """
    a, b = _fighter("Alpha"), _fighter("Beta", ability=Ability(70, 50, 80, 80))
    first = simulate_single(a, b, seed=7, key="k")
    second = simulate_single(b, a, seed=7, key="k")
    assert first.winner == second.winner


# ── 2. 주차 멱등 ──────────────────────────────────────────────────


def test_advancing_the_same_week_twice_changes_nothing():
    """**같은 주차를 두 번 진행할 수 없다** — 재시도가 전적을 두 번 올리지 않는다."""
    world = _world()
    after = engine.advance_week(world, balance=BAL).state
    again = engine.advance_week(replace(after, week=after.week - 1), balance=BAL)
    assert again.report.kind == "중복"
    assert again.state.hero.wins == after.hero.wins
    assert again.state.hero.losses == after.hero.losses


def test_week_advances_by_one():
    world = _world()
    for expected in range(2, 8):
        world = engine.advance_week(world, balance=BAL).state
        assert world.week == expected


def test_action_points_refill_each_week():
    world = _world()
    world = replace(world, action_points=0)
    world = engine.advance_week(world, balance=BAL).state
    assert world.action_points == BAL.action_points


# ── 3. 대진 ───────────────────────────────────────────────────────


def test_retired_wrestler_is_never_booked():
    """**은퇴 선수가 새 대진에 배정되지 않는다**(§7 은퇴 테스트 7)."""
    world = _world()
    retired = tuple(
        w
        if w.is_player
        else confirm(w, cause=RetirementCause.VOLUNTARY, season=1, week=1)
        for w in world.roster
    )
    world = replace(world, roster=retired)
    card = engine.book(world, balance=BAL)
    assert card.kind == "rest"
    assert card.opponent is None


def test_injured_opponents_are_excluded():
    """부상자는 후보에서 빠진다."""
    world = _world()
    hurt = tuple(
        w if w.is_player else replace(w, status=Status.INJURED, out_weeks=4)
        for w in world.roster
    )
    card = engine.book(replace(world, roster=hurt), balance=BAL)
    assert card.kind == "rest"


def test_injured_player_rests():
    world = _world()
    world = replace(
        world,
        roster=tuple(
            replace(w, out_weeks=3, status=Status.INJURED) if w.is_player else w
            for w in world.roster
        ),
    )
    card = engine.book(world, balance=BAL)
    assert card.kind == "rest"
    assert "부상" in card.note


def test_no_title_match_and_other_match_in_the_same_week():
    """대진은 **하나**다 — 타이틀전과 일반 경기를 겹쳐 넣지 않는다(§P1)."""
    world = _world()
    world = replace(
        world,
        roster=tuple(
            replace(w, popularity=90, brand="SmackDown") if w.is_player else w
            for w in world.roster
        ),
        applied=world.applied | {"shot:s1w1"},
    )
    card = engine.book(world, balance=BAL)
    assert card.kind in ("title", "single", "tag", "rest")
    if card.kind == "title":
        assert card.title is not None


def test_booking_avoids_immediate_rematches_when_pool_allows():
    """같은 상대를 연달아 붙이지 않는다(상대가 충분할 때)."""
    world = _world()
    seen = []
    for _ in range(6):
        card = engine.book(world, balance=BAL)
        if card.opponent:
            seen.append(card.opponent)
        world = engine.advance_week(world, balance=BAL).state
    # 연속 같은 이름이 둘 이상 이어지지 않는다.
    assert all(seen[i] != seen[i + 1] for i in range(len(seen) - 1))


# ── 4. 전적 일관성 ────────────────────────────────────────────────


def test_wins_plus_losses_equals_matches_played():
    """**전적이 경기 수와 맞는다**(§7 검증 5)."""
    world = _world()
    matches = 0
    for _ in range(40):
        result = engine.advance_week(world, balance=BAL)
        world = result.state
        if result.report.won is not None:
            matches += 1
    assert world.hero.wins + world.hero.losses == matches


def test_match_log_count_matches_record():
    """로그의 경기 줄 수가 전적과 맞는다 — 기록과 수치가 갈라지지 않는다."""
    world = _world()
    for _ in range(30):
        world = engine.advance_week(world, balance=BAL).state
    logged = [e for e in world.log if e.kind == "match"]
    assert len(logged) == world.hero.wins + world.hero.losses
    assert sum(1 for e in logged if e.result == "win") == world.hero.wins


def test_losing_streak_resets_on_a_win():
    world = _world()
    for _ in range(30):
        result = engine.advance_week(world, balance=BAL)
        world = result.state
        if result.report.won is True:
            assert world.hero.losing_streak == 0


def test_popularity_stays_in_bounds():
    """인기도 바닥이 10이다 — 0이면 승률이 굳어 나선에서 못 빠져나온다."""
    world = _world(style="하이플라이어")
    for _ in range(52):
        if world.phase != Phase.IN_SEASON:
            break
        world = engine.advance_week(world, balance=BAL).state
        assert BAL.min_popularity <= world.hero.popularity <= BAL.max_popularity


# ── 5. 타이틀 ─────────────────────────────────────────────────────


def _title_world(holder=None, defenses=0):
    world = _world()
    belt = Title(
        name="NXT Championship",
        brand="NXT",
        required_popularity=40,
        holder=holder,
        defenses=defenses,
        won_week=1 if holder else None,
    )
    return replace(
        world,
        titles=(belt,),
        roster=tuple(
            replace(
                w, popularity=60, held=("NXT Championship",) if holder == w.name else ()
            )
            if w.is_player
            else w
            for w in world.roster
        ),
        applied=world.applied | {"shot:s1w1"},
    )


def test_winning_a_vacant_title_records_a_reign():
    """벨트를 따면 역대 기록이 는다."""
    world = _title_world()
    for _ in range(14):
        result = engine.advance_week(world, balance=BAL)
        world = result.state
        if result.report.title_changed and result.report.won:
            assert "NXT Championship" in world.hero.reigns
            assert "NXT Championship" in world.hero.held
            champ = next(t for t in world.titles if t.name == "NXT Championship")
            assert champ.holder == world.hero.name
            return
        world = replace(world, applied=world.applied | {f"shot:s1w{world.week}"})
    pytest.skip("이 시드에서는 14주 안에 벨트를 따지 못했다")


def test_successful_defense_does_not_add_a_reign():
    """**방어는 재위를 늘리지 않는다** — 지킨 것은 새 재위가 아니다."""
    world = _title_world(holder="Hero")
    before = len(world.hero.reigns)
    for _ in range(12):
        result = engine.advance_week(world, balance=BAL)
        world = result.state
        if result.report.kind == "방어전" and result.report.won:
            assert len(world.hero.reigns) == before
            champ = next(t for t in world.titles if t.name == "NXT Championship")
            assert champ.defenses >= 1
            return
        world = replace(world, applied=world.applied | {f"shot:s1w{world.week}"})
    pytest.skip("이 시드에서는 방어전이 나오지 않았다")


def test_losing_a_defense_transfers_the_belt_and_keeps_the_record():
    """방어에 지면 벨트를 잃지만 **기록은 남는다**."""
    world = _title_world(holder="Hero")
    world = replace(
        world,
        roster=tuple(
            replace(w, reigns=("NXT Championship",)) if w.is_player else w
            for w in world.roster
        ),
    )
    for _ in range(14):
        result = engine.advance_week(world, balance=BAL)
        world = result.state
        if result.report.kind == "방어전" and result.report.won is False:
            assert "NXT Championship" not in world.hero.held
            # 역대 기록은 지워지지 않는다.
            assert "NXT Championship" in world.hero.reigns
            champ = next(t for t in world.titles if t.name == "NXT Championship")
            assert champ.holder is not None and champ.holder != world.hero.name
            return
        world = replace(world, applied=world.applied | {f"shot:s1w{world.week}"})
    pytest.skip("이 시드에서는 방어 실패가 나오지 않았다")


def test_belt_is_held_by_exactly_one_wrestler():
    """한 벨트의 주인은 한 명이다 — 전 챔피언의 `held` 에서 지워진다."""
    world = _title_world(holder="Hero")
    for _ in range(30):
        world = engine.advance_week(world, balance=BAL).state
        for belt in world.titles:
            holders = [w.name for w in world.roster if belt.name in w.held]
            assert len(holders) <= 1
            if belt.holder is not None:
                assert holders == [belt.holder]


# ── 6. 승률은 인기도 혼자 정하지 않는다 ───────────────────────────


def test_ability_matters_not_only_popularity():
    """**인기도가 높아도 기량이 낮으면 유리하지 않다**(§2.1)."""
    popular_but_weak = _fighter("Pop", popularity=95, ability=Ability(25, 80, 50, 50))
    unknown_but_strong = _fighter("Pro", popularity=20, ability=Ability(90, 30, 90, 90))
    p = win_probability(popular_but_weak, unknown_but_strong, title_match=False)
    assert p < 0.5


def test_champion_has_an_edge_in_title_matches():
    """타이틀전에서 도전자가 불리하다 — 벨트를 든 쪽이 챔피언이다."""
    a, b = _fighter("A"), _fighter("B")
    as_challenger = win_probability(a, b, title_match=True, challenger="A")
    as_champion = win_probability(a, b, title_match=True, challenger="B")
    assert as_challenger < as_champion


def test_probability_never_reaches_certainty():
    """업셋이 항상 남는다 — 0%·100% 를 말하는 시뮬레이터는 거짓이다."""
    crusher = _fighter("Crusher", popularity=100, ability=Ability(100, 100, 100, 100))
    rookie = _fighter(
        "Rookie", popularity=10, ability=Ability(1, 1, 1, 1), condition=10
    )
    p = win_probability(crusher, rookie, title_match=False)
    assert 0.12 <= p <= 0.88


def test_tag_match_needs_both_teams():
    with pytest.raises(ValueError, match="양 팀"):
        simulate_tag((), (_fighter("B"),), seed=1, key="k")


def test_tag_match_weakest_link_takes_the_fall():
    """태그는 약한 쪽이 핀을 당한다 — 평균만 쓰면 강자가 약자를 가린다."""
    strong = _fighter("Strong", ability=Ability(90, 50, 90, 90))
    weak = _fighter("Weak", ability=Ability(20, 50, 40, 40))
    other = (_fighter("X"), _fighter("Y"))
    outcome = simulate_tag((strong, weak), other, seed=4, key="k")
    assert outcome.kind == "tag"
    if outcome.loser in ("Strong", "Weak"):
        assert outcome.loser == "Weak"


# ── 시즌 경계 ─────────────────────────────────────────────────────


def test_player_retirement_ends_the_run_but_keeps_the_world():
    """플레이어가 은퇴하면 진행이 멈추지만 **세계는 남는다**(§5)."""
    world = _world()
    world = replace(
        world,
        roster=tuple(
            confirm(w, cause=RetirementCause.VOLUNTARY, season=1, week=3)
            if w.is_player
            else w
            for w in world.roster
        ),
    )
    result = engine.advance_week(world, balance=BAL)
    assert result.state.phase == Phase.SETTLEMENT
    # 로스터가 지워지지 않았다.
    assert result.state.find("Hero") is not None
    assert result.state.hero.retirement is not None
    assert result.state.retired_roster
