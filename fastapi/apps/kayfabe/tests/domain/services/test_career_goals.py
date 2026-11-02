"""시즌 목표 (`career_goals`).

**붙드는 것은 계약이다.**

1. **진행률은 세계에서 센다** — 이번 시즌 승리만, 플레이어 것만
2. **보상은 한 번만** — 같은 목표를 두 번 보상하지 않는다(`applied`)
3. **주차 진행이 보상을 준다** — `_close_week` 경로
4. **은퇴한 선수는 보상받지 않는다**
5. **보상이 인기도 상한을 넘지 않는다**
"""

from __future__ import annotations

from dataclasses import replace

from kayfabe.domain.services import career_engine as engine
from kayfabe.domain.services import career_goals as goals
from kayfabe.domain.services.career_retirement import confirm
from kayfabe.domain.services.career_world import (
    Balance,
    LogEntry,
    RetirementCause,
    Title,
)

BAL = Balance()


def _world(seed=5):
    return engine.create_world(player="Hero", style="파워", seed=seed, balance=BAL)


def _wins(state, n, *, season=None, subject="Hero"):
    s = state.season if season is None else season
    extra = tuple(
        LogEntry(season=s, week=i + 1, kind="match", subject=subject, result="win")
        for i in range(n)
    )
    return replace(state, log=state.log + extra)


def _with_popularity(state, value):
    roster = tuple(
        replace(w, popularity=value) if w.name == state.player else w
        for w in state.roster
    )
    return replace(state, roster=roster)


def _by_code(state):
    return {g.code: g for g in goals.evaluate(state)}


def test_new_world_has_three_goals_none_done():
    got = goals.evaluate(_world())
    assert [g.code for g in got] == ["season_wins", "popularity", "title"]
    assert not any(g.done or g.rewarded for g in got)


def test_season_wins_counts_only_this_season_and_player():
    w = _world()
    w = _wins(w, 4)
    w = _wins(w, 5, season=w.season + 1)  # 다른 시즌
    w = _wins(w, 7, subject="Someone")  # 남의 승리
    w = replace(
        w,
        log=w.log
        + (
            LogEntry(
                season=w.season, week=9, kind="match", subject="Hero", result="loss"
            ),
        ),
    )
    assert _by_code(w)["season_wins"].current == 4


def test_title_goal_counts_current_holder_or_won_this_season():
    w = _world()
    assert _by_code(w)["title"].current == 0
    held = replace(
        w,
        titles=(Title(name="Belt", brand="NXT", required_popularity=0, holder="Hero"),),
    )
    assert _by_code(held)["title"].done
    won = replace(
        w,
        log=w.log
        + (
            LogEntry(
                season=w.season, week=3, kind="title_won", subject="Hero", title="Belt"
            ),
        ),
    )
    assert _by_code(won)["title"].done


def test_award_is_idempotent_and_logs_once():
    w = _wins(_world(), 10)
    before = w.hero.popularity
    once = goals.award(w, balance=BAL)
    twice = goals.award(once, balance=BAL)
    assert once.hero.popularity == before + 3
    assert twice.hero.popularity == once.hero.popularity
    assert twice.applied == once.applied
    assert sum(1 for e in twice.log if e.kind == "goal") == 1
    assert _by_code(twice)["season_wins"].rewarded


def test_award_respects_popularity_cap():
    w = _with_popularity(_world(), BAL.max_popularity)
    got = goals.award(w, balance=BAL)
    assert got.hero.popularity == BAL.max_popularity
    assert _by_code(got)["popularity"].rewarded


def test_retired_player_gets_no_reward():
    w = _wins(_world(), 10)
    retired = confirm(
        w.hero, cause=RetirementCause.VOLUNTARY, season=w.season, week=w.week
    )
    w = replace(
        w,
        roster=tuple(retired if x.name == w.player else x for x in w.roster),
    )
    assert goals.award(w, balance=BAL) == w


def test_advance_week_pays_reward_through_close_week():
    w = _with_popularity(_world(), 60)
    assert not _by_code(w)["popularity"].rewarded
    after = engine.advance_week(w, balance=BAL).state
    assert _by_code(after)["popularity"].rewarded
    assert any(e.kind == "goal" for e in after.log)
