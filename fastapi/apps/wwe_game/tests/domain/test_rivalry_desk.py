"""시비를 건다 — 상대를 내가 고른다 (하네스 §3-D86).

서른 해 동안 **누구와 싸울지 한 번도 못 골랐다.** 그리고 상대가 걸어오는 쪽도
조용히 목록에 생길 뿐이라, 두 갈래가 화면에서 같은 것으로 보였다.

여기서 지키는 것 넷:

1. **막지 않는다** — §3-D85와 같은 상시 행동이다
2. **급을 넘겨 고를 수 없다** — 후보는 규칙이 쓰는 것과 같은 풀이다 (§3-D53)
3. **자리는 여전히 둘** — `MAX_ACTIVE`가 이 행동의 값이다
4. **두 갈래가 구분된다** — 내가 건 것과 상대가 걸어온 것
"""

from __future__ import annotations

import pytest
from _helpers import make_run  # noqa: I001  (tests 트리에 __init__.py가 없다)
from wwe_game.domain.entities.career_run import CareerRun, RivalryOrigin
from wwe_game.domain.exceptions import CannotCallOutError
from wwe_game.domain.services import (
    career_advance,
    rivalry_desk,
    rivalry_engine,
    seeded_roll,
)
from wwe_game.domain.services.seeded_roll import SeededRoll
from wwe_game.domain.value_objects.advance_outcome import StopReason
from wwe_game.domain.value_objects.contract import Contract
from wwe_game.domain.value_objects.quarter_goal import QuarterGoal, quarter_of
from wwe_game.domain.value_objects.wrestler_stats import WrestlerStats

WEEK = 300
SOLID = WrestlerStats(popularity=70, in_ring=70, mic_work=60, backstage=70)


def ready() -> CareerRun:
    """대립이 하나도 없고 걸 수 있는 상태. 목표·계약을 채워 멈춤을 비켜 둔다."""
    return make_run(week=WEEK, stats=SOLID).evolve(
        rivalries=(),
        contract=Contract(
            weekly_pay=3_000, signed_week=WEEK - 10, ends_week=WEEK + 200
        ),
        goal=QuarterGoal.DRIFT,
        goal_quarter=quarter_of(WEEK),
    )


class TestItDoesNotBlock:
    def test_the_week_runs_whether_you_call_out_or_not(self) -> None:
        """**상시 행동이다** (§3-D85와 같은 자리) — 안 걸어도 진행된다."""
        assert career_advance.advance(ready()).run.week > WEEK

    def test_there_is_no_stop_reason_for_it(self) -> None:
        assert "call_out" not in {r.value for r in StopReason}
        assert "rivalry" not in {r.value for r in StopReason}


class TestTheCandidates:
    def test_they_come_from_the_pool_the_rule_uses(self) -> None:
        """**규칙과 화면이 같은 풀을 본다** — 아니면 "화면엔 뜨는데 규칙은 모르는" 상대가 생긴다."""
        run = ready()
        pool = set(rivalry_engine.candidate_pool(run))
        assert pool, "후보 풀이 비면 이 규칙을 잴 수 없다"
        assert set(rivalry_desk.candidates(run)) <= pool

    def test_the_list_survives_a_reload(self) -> None:
        """**새로고침해도 같다** (§3-D4). 아니면 목록을 다시 굴리는 것이 최적 플레이가 된다."""
        run = ready()
        assert rivalry_desk.candidates(run) == rivalry_desk.candidates(run)

    def test_it_never_offers_more_than_a_handful(self) -> None:
        """전부 늘어놓으면 고르는 것이 아니라 검색이 된다."""
        picked = rivalry_desk.candidates(ready())
        assert 0 < len(picked) <= rivalry_desk.MAX_CANDIDATES
        assert len(set(picked)) == len(picked), "같은 사람이 두 번 서면 안 된다"

    def test_it_never_offers_me(self) -> None:
        run = ready()
        assert str(run.identity.name) not in rivalry_desk.candidates(run)

    def test_it_never_offers_someone_already_in_a_feud(self) -> None:
        run = ready()
        first = rivalry_desk.candidates(run)[0]
        after = rivalry_desk.call_out(run, first)
        assert first not in rivalry_desk.candidates(after)


class TestTheSlots:
    def test_a_full_card_cannot_take_another(self) -> None:
        """**자리가 이 행동의 값이다** — 내가 고른 상대가 규칙의 이야기를 밀어낸다."""
        run = ready()
        for _ in range(rivalry_engine.MAX_ACTIVE):
            run = rivalry_desk.call_out(run, rivalry_desk.candidates(run)[0])
        assert len(run.rivalries) == rivalry_engine.MAX_ACTIVE
        assert not rivalry_desk.can_call_out(run)
        assert rivalry_desk.candidates(run) == ()
        with pytest.raises(CannotCallOutError):
            rivalry_desk.call_out(run, "아무나")

    def test_a_closed_career_cannot_call_out(self) -> None:
        from wwe_game.domain.entities.career_run import EndReason

        assert not rivalry_desk.can_call_out(ready().ended(EndReason.PLAYER))


class TestOffTheList:
    def test_a_name_outside_the_list_is_refused(self) -> None:
        """**목록 밖은 거절한다** — 체험판은 세이브를 들고 다니므로(§3-D8) 특히 필요하다.

        안 막으면 요청 한 줄로 루키가 메인이벤터와 붙고 §3-D53의 그림이 무너진다.
        """
        with pytest.raises(CannotCallOutError):
            rivalry_desk.call_out(ready(), "존재하지 않는 사람")

    def test_someone_in_the_pool_but_not_offered_is_refused(self) -> None:
        """풀에 있어도 **이번 목록에 없으면** 못 건다 — 목록이 곧 선택지다."""
        run = ready()
        offered = set(rivalry_desk.candidates(run))
        rest = [n for n in rivalry_engine.candidate_pool(run) if n not in offered]
        if not rest:
            pytest.skip("풀이 후보 수보다 크지 않다")
        with pytest.raises(CannotCallOutError):
            rivalry_desk.call_out(run, rest[0])


class TestTheTwoOrigins:
    """**두 갈래가 같은 대립이 아니다** (§3-D86)."""

    def test_calling_out_is_marked_as_mine(self) -> None:
        run = ready()
        name = rivalry_desk.candidates(run)[0]
        opened = rivalry_desk.call_out(run, name)
        fresh = next(r for r in opened.rivalries if r.rival_name == name)
        assert fresh.opened_by is RivalryOrigin.PLAYER

    def test_the_rule_opens_them_as_theirs(self) -> None:
        """규칙이 여는 대립은 전부 **상대가 걸어온 것**이다."""
        run = ready()
        opened = rivalry_engine.start_rivalry(
            run, WEEK, SeededRoll(run.seed, WEEK, seeded_roll.RIVALRY)
        )
        assert opened is not None
        assert opened.opened_by is RivalryOrigin.RIVAL

    def test_old_saves_read_as_theirs(self) -> None:
        """옛 세이브에는 이 칸이 없다 — 그때의 대립은 전부 규칙이 열었다."""
        from wwe_game.domain.entities.career_run import Rivalry, RivalryStage

        old = Rivalry(
            rival_name="아무개", stage=RivalryStage.HEATED, heat=40, started_week=10
        )
        assert old.opened_by is RivalryOrigin.RIVAL

    def test_both_sides_start_at_the_same_heat(self) -> None:
        """**여는 자리는 하나다** — 갈리는 것은 누가 걸었는가뿐이다."""
        mine = rivalry_engine.open_with("갑", WEEK, by=RivalryOrigin.PLAYER)
        theirs = rivalry_engine.open_with("을", WEEK)
        assert mine.heat == theirs.heat
        assert mine.stage is theirs.stage


class TestItFeedsTheRules:
    def test_the_one_i_called_out_becomes_my_opponent(self) -> None:
        """고른 상대가 실제로 링에 선다 — 아니면 고른 것이 장식이다."""
        run = ready()
        name = rivalry_desk.candidates(run)[0]
        opened = rivalry_desk.call_out(run, name)
        roll = SeededRoll(opened.seed, WEEK, seeded_roll.OPPONENT)
        assert rivalry_engine.pick_opponent(opened, roll) == name
