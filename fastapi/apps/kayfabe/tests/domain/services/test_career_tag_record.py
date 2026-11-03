"""태그전 전적. **플레이어 본인 전적은 맞고, 나머지 셋의 전적이 틀린다**(알려진 결함).

## 결함의 실제 경로 (Phase 0.5 · 2026-11-03 추적)

`simulate_tag` 는 `winner` = 이긴 팀에서 핀을 딴 선수, `loser` = 진 팀에서 핀을
당한 선수를 돌려준다. `_apply_outcome` 는

    won       = 플레이어 팀이 이겼나     ← 팀 단위로 맞게 센다
    foe_name  = loser if winner == 플레이어 else winner

로 **상대 한 명**을 고르고, 그 선수에게 `won` 의 반대를 적는다. 싱글 경기에서는
맞는 식이지만 태그에서는 `winner` 가 **같은 편 파트너**일 수 있다:

    파트너가 핀을 땄다(팀 승)  → foe_name = 파트너 → **파트너에게 패배**
                                 핀을 당한 상대는 기록 없음
    상대가 플레이어를 핀했다    → 상대 득점자에게 승리 (맞음) · 파트너 기록 없음
    상대가 파트너를 핀했다      → 상대 득점자에게 승리 (맞음) · 파트너 기록 없음
    플레이어가 핀을 땄다        → 핀당한 상대에게 패배 (맞음) · 파트너 기록 없음

골든 시즌(시드 11) 태그 18경기 중 첫째 줄이 1번(w33) 나왔다. 연승 카운터
(`career_tally.step`)도 같은 `foe` 에 붙어 있어 같은 오류를 따른다.

## 이 파일이 하는 일

**동작을 바꾸지 않는다.** 올바른 기대값을 `xfail(strict=True)` 로 적어 둔다 —
지금은 실패가 정상이고, 고치는 순간 XPASS 로 깨져 표시를 떼라고 알린다.
골든 기준값은 이 결함을 포함한 채 그대로다. 고치면 골든이 **의도적으로** 바뀐다.
"""

from __future__ import annotations

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


# ── 지금도 맞는 것 — Phase 2 에서 깨지면 안 된다 ──────────────────


@pytest.mark.parametrize(
    ("scorer", "pinned", "team_won"),
    [
        (ME, FOE_1, True),
        (PARTNER, FOE_2, True),
        (FOE_1, ME, False),
        (FOE_2, PARTNER, False),
    ],
)
def test_player_record_is_team_level(scorer: str, pinned: str, team_won: bool) -> None:
    """플레이어 본인은 **누가 핀을 땄든** 팀 결과대로 1승 또는 1패."""
    after = _tag(_world(), scorer=scorer, pinned=pinned)

    assert _record(after, ME) == ((1, 0) if team_won else (0, 1))


def test_reproduces_partner_loss_on_partner_pin() -> None:
    """**현재 동작 재현.** 파트너가 핀을 따 팀이 이겼는데 파트너에게 패배가 붙는다."""
    after = _tag(_world(), scorer=PARTNER, pinned=FOE_2)

    assert _record(after, PARTNER) == (0, 1)
    assert _record(after, FOE_2) == (0, 0)
    assert after.require(PARTNER).losing_streak == 1


# ── 올바른 기대값 — 지금은 실패가 정상이다 ────────────────────────


@pytest.mark.xfail(
    strict=True,
    reason="알려진 결함: 태그전 foe_name 이 같은 편 득점자를 가리킨다 (Phase 2 수정 예정)",
)
def test_partner_who_scores_gets_a_win() -> None:
    after = _tag(_world(), scorer=PARTNER, pinned=FOE_2)

    assert _record(after, PARTNER) == (1, 0)


@pytest.mark.xfail(
    strict=True,
    reason="알려진 결함: 태그전에서 핀을 당한 상대가 기록되지 않는다 (Phase 2 수정 예정)",
)
def test_pinned_opponent_gets_a_loss_when_partner_scores() -> None:
    after = _tag(_world(), scorer=PARTNER, pinned=FOE_2)

    assert _record(after, FOE_2) == (0, 1)
