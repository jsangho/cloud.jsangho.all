"""태그전 전적. **팀 전원이 팀 결과대로 1승 또는 1패를 받는다.**

## 있던 결함 (2026-11-06 수정)

`simulate_tag` 의 `winner`·`loser` 는 핀을 따고 당한 **개인**이다. `_apply_outcome` 는
이 둘로 상대 한 명을 골라 싱글처럼 처리했다.

    파트너가 핀을 땄다(팀 승)  → 파트너에게 **패배** · 핀을 당한 상대는 기록 없음
    그 밖의 경우                → 네 명 중 두 명만 기록

플레이어 본인은 처음부터 팀 단위로 셌으므로 네 명의 전적이 서로 맞지 않았다.

## 전적만 고쳤다

피로(`condition`·`consecutive_matches`)는 예전처럼 한 명만 받는다. 전원에게 주면 NPC
경기력이 달라져 200시드 중 19개의 시즌 궤적이 바뀐다 — 그것은 밸런스 판단이다. 전적만
고치면 200시드 전부 플레이어의 주차별 결과가 그대로였다. 그래서 골든의 주차 보고가
기준값으로 남는다(`test_career_golden`).
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from kayfabe.domain.services import career_engine as engine
from kayfabe.domain.services.career_match import MATCH_TAG, MatchOutcome
from kayfabe.domain.services.career_world import Balance, WorldState

ME = "Ho"
PARTNER = "Dex Harlow"
FOE_1 = "Marcus Vane"
FOE_2 = "Rio Castellan"


def _world() -> WorldState:
    return engine.create_world(player=ME, style="파워", seed=1)


def _tag(world: WorldState, *, scorer: str, pinned: str) -> WorldState:
    """태그 결과 하나를 반영한다. 뽑기 없이 결과를 직접 준다."""
    outcome = MatchOutcome(
        kind=MATCH_TAG,
        winner=scorer,
        loser=pinned,
        probability=0.5,
        roll=0.1,
        finish="핀폴",
        rating=50,
        team_a=(ME, PARTNER),
        team_b=(FOE_1, FOE_2),
    )
    card = engine.Card(
        kind="tag", opponent=FOE_1, partner=PARTNER, opponents=(FOE_1, FOE_2)
    )
    state, _ = engine._apply_outcome(
        world, outcome=outcome, card=card, balance=Balance()
    )
    return state


def _record(world: WorldState, name: str) -> tuple[int, int]:
    w = world.require(name)
    return w.wins, w.losses


_WIN = (1, 0)
_LOSS = (0, 1)
_RESULTS = [
    pytest.param(ME, FOE_1, True, id="player-scores"),
    pytest.param(PARTNER, FOE_2, True, id="partner-scores"),
    pytest.param(FOE_1, ME, False, id="player-pinned"),
    pytest.param(FOE_2, PARTNER, False, id="partner-pinned"),
]


@pytest.mark.parametrize(("scorer", "pinned", "team_won"), _RESULTS)
def test_all_four_get_the_team_result(scorer: str, pinned: str, team_won: bool) -> None:
    after = _tag(_world(), scorer=scorer, pinned=pinned)

    mine, theirs = (_WIN, _LOSS) if team_won else (_LOSS, _WIN)
    assert [_record(after, name) for name in (ME, PARTNER)] == [mine, mine]
    assert [_record(after, name) for name in (FOE_1, FOE_2)] == [theirs, theirs]


@pytest.mark.parametrize(("scorer", "pinned", "team_won"), _RESULTS)
def test_streaks_follow_the_team_result(
    scorer: str, pinned: str, team_won: bool
) -> None:
    after = _tag(_world(), scorer=scorer, pinned=pinned)

    for name in (PARTNER, FOE_1, FOE_2):
        w = after.require(name)
        won = (name == PARTNER) == team_won
        assert w.win_streak == (1 if won else 0), name
        assert w.best_win_streak == (1 if won else 0), name
        assert w.losing_streak == (0 if won else 1), name


@pytest.mark.parametrize(("scorer", "pinned", "team_won"), _RESULTS)
def test_wins_and_losses_stay_balanced(
    scorer: str, pinned: str, team_won: bool
) -> None:
    after = _tag(_world(), scorer=scorer, pinned=pinned)

    assert sum(w.wins for w in after.roster) == sum(w.losses for w in after.roster)


@pytest.mark.parametrize(
    ("scorer", "pinned", "tired"),
    [
        (ME, FOE_1, FOE_1),
        (PARTNER, FOE_2, PARTNER),
        (FOE_1, ME, FOE_1),
        (FOE_2, PARTNER, FOE_2),
    ],
)
def test_only_one_npc_gets_tired(scorer: str, pinned: str, tired: str) -> None:
    """**밸런스를 움직이지 않는다는 고정.** 전원에게 주면 궤적이 바뀐다."""
    world = _world()
    after = _tag(world, scorer=scorer, pinned=pinned)

    for name in (PARTNER, FOE_1, FOE_2):
        before, now = world.require(name), after.require(name)
        if name == tired:
            assert now.condition == max(10, before.condition - 8)
            assert now.consecutive_matches == before.consecutive_matches + 1
        else:
            assert now.condition == before.condition
            assert now.consecutive_matches == before.consecutive_matches


def test_a_lost_streak_is_broken_by_a_partner_pin() -> None:
    """예전에는 이 경기가 파트너의 연패를 **늘렸다.**"""
    world = _world()
    roster = tuple(
        replace(w, losing_streak=3, win_streak=0) if w.name == PARTNER else w
        for w in world.roster
    )
    after = _tag(replace(world, roster=roster), scorer=PARTNER, pinned=FOE_2)

    assert after.require(PARTNER).losing_streak == 0


def test_a_participant_missing_from_the_roster_is_skipped() -> None:
    world = _world()
    roster = tuple(w for w in world.roster if w.name != FOE_2)

    after = _tag(replace(world, roster=roster), scorer=PARTNER, pinned=FOE_1)

    assert after.find(FOE_2) is None
    assert _record(after, PARTNER) == _WIN
    assert _record(after, FOE_1) == _LOSS


def test_player_listed_on_the_second_team_keeps_sides_straight() -> None:
    outcome = MatchOutcome(
        kind=MATCH_TAG,
        winner=FOE_1,
        loser=PARTNER,
        probability=0.5,
        roll=0.1,
        finish="핀폴",
        rating=50,
        team_a=(FOE_1, FOE_2),
        team_b=(ME, PARTNER),
    )

    results = dict(engine._other_results(outcome, me=ME, won=False))

    assert results == {PARTNER: False, FOE_1: True, FOE_2: True}


def test_a_single_match_still_touches_exactly_one_opponent() -> None:
    outcome = MatchOutcome(
        kind="single",
        winner=ME,
        loser=FOE_1,
        probability=0.5,
        roll=0.1,
        finish="핀폴",
        rating=50,
        team_a=(ME,),
        team_b=(FOE_1,),
    )

    assert engine._other_results(outcome, me=ME, won=True) == ((FOE_1, False),)
