"""경기 기록(`MatchRecord`). **기존에 계산된 값과 한 칸도 어긋나지 않는다.**

근거 궤적은 골든(시드 11 · 52주 · 태그 18경기 포함)이다. 기록은 골든 기준값을
바꾸지 않고(`test_career_golden`) 여기서는 기록 자체가 맞는지를 본다:

1. **일치** — 승률은 `WeekReport`, 피니시·평점은 로그 문장, 타이틀은 벨트 이동,
   인기도 변화는 `WeekReport` 와 같다
2. **캡처 시점** — `before` 는 결과 반영 직전, `after` 는 반영·부상 직후이고 주차
   마감의 목표 보상은 빠진다
3. **참가자** — 싱글 2명 · 태그 4명, 팀 순서, 핀폴일 때만 득점자
4. **불변·중복·상한** — 기록은 붙기만 하고, 같은 id 는 한 번, 104건에서 오래된 것부터
"""

from __future__ import annotations

import ast
import importlib.util
import inspect
from dataclasses import replace
from pathlib import Path

import pytest

from kayfabe.domain.services import career_actions as actions
from kayfabe.domain.services import career_engine as engine
from kayfabe.domain.services import career_events as events
from kayfabe.domain.services import career_goals as goals
from kayfabe.domain.services import career_match_record as records
from kayfabe.domain.services import career_season as season_rules
from kayfabe.domain.services.career_world import (
    STATE_FIELDS,
    Balance,
    MatchRecord,
    Phase,
    WorldState,
)

_GOLDEN_PATH = Path(__file__).resolve().parent / "test_career_golden.py"


def _golden():
    spec = importlib.util.spec_from_file_location("_career_golden_mr", _GOLDEN_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def golden_run():
    g = _golden()
    weeks, world = g.run_trajectory()
    return weeks, world


def _record(world: WorldState, season: int, week: int) -> MatchRecord | None:
    rid = records.match_id(season=season, week=week)
    return next((m for m in world.matches if m.id == rid), None)


def _match_reports(weeks):
    return [w["report"] for w in weeks if w["report"]["opponent"] is not None]


IDX = {name: i for i, name in enumerate(STATE_FIELDS)}


# ── 저장 형식 ─────────────────────────────────────────────────────


def test_state_fields_order_is_the_storage_format() -> None:
    """배열 인덱스의 뜻. **이 순서가 바뀌면 옛 기록이 다른 숫자로 읽힌다.**"""
    assert STATE_FIELDS == (
        "popularity",
        "condition",
        "wins",
        "losses",
        "win_streak",
        "losing_streak",
    )


def test_record_module_draws_no_random_numbers() -> None:
    """기록은 뽑기를 하지 않는다 — 난수 모듈을 **import 하지 않는 것**으로 보장한다.

    문자열 검색이 아니라 import 문만 본다(독스트링이 그 이름을 설명으로 적는다).
    """
    tree = ast.parse(inspect.getsource(records))
    imported = {
        node.module if isinstance(node, ast.ImportFrom) else alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert not any("career_rng" in (m or "") or "random" in (m or "") for m in imported)


# ── 1. 기존 값과의 일치 ──────────────────────────────────────────


def test_every_match_week_has_exactly_one_record(golden_run) -> None:
    weeks, world = golden_run
    reports = _match_reports(weeks)

    assert len(world.matches) == len(reports) == 40
    assert [m.id for m in world.matches] == [
        records.match_id(season=r["season"], week=r["week"]) for r in reports
    ]
    assert len({m.id for m in world.matches}) == len(world.matches)


def test_record_matches_week_report(golden_run) -> None:
    """승률 · 피니시 · 평점 · 타이틀 · 인기도 변화 · 승패 · 부상이 `WeekReport` 와 같다."""
    weeks, world = golden_run
    for r in _match_reports(weeks):
        m = _record(world, r["season"], r["week"])
        assert m is not None
        assert m.probability == r["probability"]
        assert m.finish == r["finish"]
        assert m.rating == r["rating"]
        assert m.title == r["title"]
        assert m.title_changed == r["title_changed"]
        assert m.popularity_delta == r["popularity_delta"]
        assert (m.winner_side == 0) == r["won"]
        assert (m.injury.kind if m.injury else None) == r["injured"]


def test_record_matches_log_sentence_and_belts(golden_run) -> None:
    """피니시·평점은 로그 문장 그대로, 타이틀 이동은 `title_won` 로그와 같다."""
    _, world = golden_run
    for m in world.matches:
        line = next(
            e
            for e in world.log
            if e.kind == "match" and (e.season, e.week) == (m.season, m.week)
        )
        assert f"({m.finish} · 평가 {m.rating})" in line.summary
        assert line.result == ("win" if m.winner_side == 0 else "loss")
        assert line.title == m.title
        won_belt = any(
            e.kind == "title_won" and (e.season, e.week) == (m.season, m.week)
            for e in world.log
        )
        assert won_belt == m.title_changed


def test_title_changed_record_names_the_new_holder(golden_run) -> None:
    """벨트가 넘어간 경기의 승리 팀에 그 벨트의 새 주인이 있다."""
    _, world = golden_run
    changed = [m for m in world.matches if m.title_changed]
    assert changed
    for m in changed:
        holder = next(
            e.subject
            for e in world.log
            if e.kind == "title_won" and (e.season, e.week) == (m.season, m.week)
        )
        assert holder in m.teams[m.winner_side]


# ── 2. 캡처 시점 ─────────────────────────────────────────────────


def _step_with_records(world: WorldState, bal: Balance):
    """한 주를 진행하고 (진행 전 세계, 진행 후 세계, 그 주 기록) 을 준다."""
    after = engine.advance_week(world, balance=bal).state
    new = [m for m in after.matches if m not in world.matches]
    return world, after, (new[0] if new else None)


def test_before_is_the_state_right_before_the_result() -> None:
    """`before` = 진행 직전 로스터. 경기 분기에서는 시뮬레이션 전에 상태가 바뀌지 않는다."""
    bal = Balance()
    world = engine.create_world(player="Rec", style="파워", seed=11)
    checked = 0
    for _ in range(30):
        prev, world, rec = _step_with_records(world, bal)
        if rec is None:
            continue
        for p in rec.participants:
            assert p.before == records.state_of(prev.require(p.name)), p.name
        checked += 1
    assert checked >= 10


def test_after_excludes_goal_rewards_and_includes_injury() -> None:
    """`after` 는 결과·부상 반영 직후다. **목표 보상 인기도는 빠진다.**

    NPC 는 주차 마감에서 바뀌지 않으므로 진행 후 로스터와 같아야 하고, 플레이어
    인기도는 그 주에 지급된 목표 보상만큼 진행 후 값보다 작아야 한다.
    """
    bal = Balance()
    world = engine.create_world(player="Rec", style="파워", seed=11)
    rewarded_weeks = injured_weeks = 0
    for _ in range(52):
        prev, world, rec = _step_with_records(world, bal)
        if rec is None:
            if world.phase != Phase.IN_SEASON:
                break
            continue
        reward = sum(
            spec.reward_popularity
            for spec in goals.SEASON_GOALS
            if goals.goal_key(season=rec.season, code=spec.code) in world.applied
            and goals.goal_key(season=rec.season, code=spec.code) not in prev.applied
        )
        for p in rec.participants:
            now = records.state_of(world.require(p.name))
            if p.name != world.player:
                assert p.after == now, p.name
                continue
            # 인기도 말고는 주차 마감이 바꾸지 않는다.
            assert p.after[1:] == now[1:]
            # 인기도는 목표 보상만큼 차이 난다 — 상한에 걸리면 그보다 작게.
            gap = now[IDX["popularity"]] - p.after[IDX["popularity"]]
            if now[IDX["popularity"]] < bal.max_popularity:
                assert gap == reward
            else:
                assert 0 <= gap <= reward
        rewarded_weeks += reward > 0
        injured_weeks += rec.injury is not None
    assert rewarded_weeks >= 1, (
        "목표 보상이 지급된 경기 주차가 있어야 이 테스트가 의미가 있다"
    )


def test_player_injury_lowers_after_condition() -> None:
    """부상은 `after` 에 들어간다 — 부상 판정은 경기 후 사진보다 먼저다."""
    bal = Balance()
    found = False
    for seed in range(1, 60):
        world = engine.create_world(player="Rec", style="하이플라이어", seed=seed)
        for _ in range(52):
            prev, world, rec = _step_with_records(world, bal)
            me = (
                next(p for p in rec.participants if p.name == world.player)
                if rec is not None and rec.injury is not None
                else None
            )
            # 컨디션 하한(10)에 걸리지 않는 경기만 본다 — 걸리면 깎일 자리가 없다.
            if me is not None and me.before[IDX["condition"]] >= 40:
                now = records.state_of(world.require(world.player))
                # 부상으로 깎인 컨디션이 `after` 에 있다(인기도 칸은 목표 보상 때문에 뺀다).
                assert me.after[1:] == now[1:]
                assert me.after[IDX["condition"]] < me.before[IDX["condition"]]
                found = True
                break
            if world.phase != Phase.IN_SEASON:
                break
        if found:
            break
    assert found, "부상 경기를 찾지 못했다"


# ── 3. 참가자 ────────────────────────────────────────────────────


def test_single_has_two_and_tag_has_four_participants(golden_run) -> None:
    _, world = golden_run
    tags = [m for m in world.matches if m.kind == "tag"]
    singles = [m for m in world.matches if m.kind != "tag"]
    assert len(tags) == 18 and singles
    for m in singles:
        assert [len(t) for t in m.teams] == [1, 1]
        assert len(m.participants) == 2
    for m in tags:
        assert [len(t) for t in m.teams] == [2, 2]
        assert len(m.participants) == 4
        assert m.teams[0][0] == world.player
    for m in world.matches:
        assert [(p.name, p.side) for p in m.participants] == [
            (n, s) for s, team in enumerate(m.teams) for n in team
        ]
        assert m.teams[0][0] == world.player
        assert all(
            len(p.before) == len(p.after) == len(STATE_FIELDS) for p in m.participants
        )


def test_finisher_scorer_pinned_roles(golden_run) -> None:
    """`finisher` 는 항상 이긴 팀 안에 있다. `scorer`·`pinned` 는 **핀폴일 때만** 있다."""
    _, world = golden_run
    finishes = {m.finish for m in world.matches}
    assert records.PINFALL in finishes and finishes - {records.PINFALL}
    for m in world.matches:
        assert m.finisher in m.teams[m.winner_side]
        if m.finish == records.PINFALL:
            assert m.scorer == m.finisher
            assert m.pinned in m.teams[1 - m.winner_side]
        else:
            assert m.scorer is None and m.pinned is None


def test_power_is_what_the_simulation_used(golden_run) -> None:
    """`power` 의 합이 기록된 승률을 다시 만든다(싱글 · 비타이틀)."""
    _, world = golden_run
    checked = 0
    for m in world.matches:
        if m.kind != "single":
            continue
        a, b = (sum(p.power) for p in m.participants)
        expected = max(0.12, min(0.88, 0.5 + (a - b) * 0.9))
        assert m.probability == pytest.approx(expected, abs=1e-12)
        checked += 1
    assert checked


def test_every_participant_record_matches_the_winning_side(golden_run) -> None:
    """참가자 전원의 `after` 전적이 `winner_side` 와 맞는다 — 싱글도, 태그도.

    파트너가 득점해 이긴 태그전(골든 w33)이 있어야 의미가 있다. 예전에는 그 경기에서
    파트너가 패배를 받고 상대 팀은 기록이 없었다.
    """
    _, world = golden_run
    assert any(
        m.kind == "tag" and m.winner_side == 0 and m.finisher != world.player
        for m in world.matches
    ), "파트너 득점 승리 태그전이 골든에 있어야 한다(w33)"

    for m in world.matches:
        for p in m.participants:
            won = p.side == m.winner_side
            assert p.after[IDX["wins"]] - p.before[IDX["wins"]] == (1 if won else 0)
            assert p.after[IDX["losses"]] - p.before[IDX["losses"]] == (0 if won else 1)
            assert p.after[IDX["win_streak"]] == (
                p.before[IDX["win_streak"]] + 1 if won else 0
            )
            assert p.after[IDX["losing_streak"]] == (
                0 if won else p.before[IDX["losing_streak"]] + 1
            )


def test_heat_changes_are_only_real_changes(golden_run) -> None:
    _, world = golden_run
    assert any(m.heat for m in world.matches)
    for m in world.matches:
        names = {p.name for p in m.participants}
        for h in m.heat:
            assert h.a in names and h.b in names and h.a != h.b
            assert h.before != h.after


# ── 4. 불변 · 중복 · 상한 ────────────────────────────────────────


def test_records_only_grow_through_a_season() -> None:
    """행동·사건·주차·결산·다음 시즌 어디에서도 **이미 있는 기록은 바뀌지 않는다.**"""
    g = _golden()
    bal = Balance()
    world = engine.create_world(player=g.PLAYER, style="테크니션", seed=g.SEED, age=26)
    for i in range(bal.season_weeks):
        kept = world.matches
        try:
            world = actions.perform(
                world, action=("훈련", "프로모", "휴식")[i % 3], balance=bal
            )
        except ValueError:
            pass
        assert world.matches == kept
        for event in list(world.pending):
            code = next(
                (c.code for c in event.choices if c.enabled and c.code != "retire"),
                None,
            )
            if code:
                world = events.resolve(
                    world, event_id_=event.id, choice_code=code, balance=bal
                )
        assert world.matches == kept
        world = engine.advance_week(world, balance=bal).state
        assert world.matches[: len(kept)] == kept
        assert len(world.matches) - len(kept) in (0, 1)
        if world.phase != Phase.IN_SEASON:
            break
    kept = world.matches
    world = season_rules.settle(world, balance=bal)
    assert world.matches == kept
    world = season_rules.start_next_season(world, balance=bal)
    assert world.matches == kept


def test_same_id_is_appended_once(golden_run) -> None:
    _, world = golden_run
    again = records.append(world, world.matches[-1])
    assert again is world


def test_replaying_a_week_does_not_duplicate_the_record() -> None:
    """같은 주차 키로 다시 들어와도(저장 실패 후 재진입) 기록이 두 번 생기지 않는다."""
    bal = Balance()
    world = engine.create_world(player="Rec", style="파워", seed=11)
    for _ in range(4):
        world = engine.advance_week(world, balance=bal).state
    rewound = replace(world, week=world.week - 1)

    again = engine.advance_week(rewound, balance=bal).state

    assert again.matches == rewound.matches


def _fake(i: int) -> MatchRecord:
    return replace(
        _golden_first(),
        id=records.match_id(season=1 + i // 52, week=1 + i % 52),
        season=1 + i // 52,
        week=1 + i % 52,
    )


_FIRST: list[MatchRecord] = []


def _golden_first() -> MatchRecord:
    if not _FIRST:
        _, world = _golden().run_trajectory()
        _FIRST.append(world.matches[0])
    return _FIRST[0]


def test_cap_keeps_the_newest_104_in_order() -> None:
    world = engine.create_world(player="Rec", style="파워", seed=1)
    made = [_fake(i) for i in range(records.MAX_MATCH_RECORDS + 6)]
    for m in made:
        world = records.append(world, m)

    assert len(world.matches) == records.MAX_MATCH_RECORDS == 104
    assert list(world.matches) == made[6:]


# ── 기록이 없는 경기의 사유 ──────────────────────────────────────


def test_missing_reason_distinguishes_before_records_and_trimmed() -> None:
    world = engine.create_world(player="Rec", style="파워", seed=1)
    made = [_fake(i) for i in range(records.MAX_MATCH_RECORDS + 6)]
    for m in made:
        world = records.append(world, m)

    # 새 커리어(since=None) — 잘린 경기는 trimmed, 남은 경기는 None.
    assert records.missing_reason(world, season=1, week=1) == records.TRIMMED
    assert (
        records.missing_reason(world, season=made[6].season, week=made[6].week) is None
    )

    # 업그레이드된 커리어 — since 이전은 before_records.
    upgraded = replace(world, match_records_since=(1, 3))
    assert records.missing_reason(upgraded, season=1, week=2) == records.BEFORE_RECORDS
    assert records.missing_reason(upgraded, season=1, week=4) == records.TRIMMED

    # 남은 기록보다 뒤인데 없다 — 자기모순.
    assert records.missing_reason(world, season=9, week=1) == records.UNEXPLAINED


def test_new_career_records_from_debut() -> None:
    world = engine.create_world(player="Rec", style="파워", seed=1)
    assert world.match_records_since is None
    assert world.matches == ()
