"""가방을 언제 쓸까 (하네스 §3-D85).

§3-D36이 `CASH_IN_PENDING` 표식을 두고 `week_simulation`이 그걸 읽고 있었는데
**아무도 세우지 않았다** — 52주가 지나면 규칙이 알아서 현금화했고, 머니 인 더 뱅크의
전부인 *"언제 뛰어드느냐"*가 통째로 자동이었다.

여기서 지키는 것 넷:

1. **막지 않는다** — 가방을 들고 있어도 진행은 그대로 흐른다 (§3-D80·D84와 다르다)
2. 쓸 수 없는 자리에서는 **안 열린다** (무소속 · 이미 그 벨트 · 이미 정함)
3. 정하면 **다음 경기 주차에 타이틀전이 걸린다** — 규칙이 표식을 읽는다
4. 시계는 그대로다 — 안 쓰면 52주에 규칙이 대신 쓴다
"""

from __future__ import annotations

import pytest
from _helpers import make_run  # noqa: I001  (tests 트리에 __init__.py가 없다)
from wwe_game.domain.constants import career_rules as rules
from wwe_game.domain.constants.career_flags import CASH_IN_PENDING
from wwe_game.domain.entities.career_run import CareerRun
from wwe_game.domain.exceptions import CannotCashInError
from wwe_game.domain.services import briefcase_desk, career_advance, championship
from wwe_game.domain.value_objects.advance_outcome import StopReason
from wwe_game.domain.value_objects.contract import Contract
from wwe_game.domain.value_objects.quarter_goal import QuarterGoal, quarter_of
from wwe_game.domain.value_objects.title import Brand
from wwe_game.domain.value_objects.wrestler_stats import WrestlerStats

WEEK = 300
"""가방을 든 주차. 계약이 살아 있어야 협상(§3-D84)이 측정에 안 섞인다."""

SOLID = WrestlerStats(popularity=70, in_ring=70, mic_work=60, backstage=70)


def carrying(*, won_at: int = WEEK - 17, brand: Brand = Brand.RAW) -> CareerRun:
    """가방을 든 세이브. 기본은 딴 지 17주 지난 상태다.

    **목표와 계약을 미리 채워 둔다** — 안 채우면 `advance`가 `GOAL`·`OFFER`에서
    먼저 서서(§3-D80·D84) "가방이 진행을 막지 않는다"를 잴 수가 없다.
    """
    return make_run(week=WEEK, stats=SOLID, brand=brand).evolve(
        briefcase_week=won_at,
        contract=Contract(
            weekly_pay=3_000, signed_week=WEEK - 10, ends_week=WEEK + 200
        ),
        goal=QuarterGoal.DRIFT,
        goal_quarter=quarter_of(WEEK),
    )


class TestItDoesNotBlock:
    """**여기가 §3-D80·D84와 갈리는 자리다.** 목표·협상은 멈춤이고 이건 상시 행동이다."""

    def test_carrying_it_never_stops_the_week(self) -> None:
        outcome = career_advance.advance(carrying())
        assert outcome.stop_reason is not StopReason.OFFER
        assert outcome.run.week > WEEK, "가방을 들었다고 진행이 멈추면 안 된다"

    def test_deciding_does_not_stop_the_week_either(self) -> None:
        """정한 뒤에도 막지 않는다 — 규칙이 다음 경기 주차에 알아서 건다."""
        decided = briefcase_desk.cash_in(carrying())
        assert career_advance.advance(decided).run.week > WEEK

    def test_there_is_no_stop_reason_for_it(self) -> None:
        """**멈춤을 더하지 않았다.** 더하면 FM의 '다음'과 반대로 간다."""
        assert "briefcase" not in {r.value for r in StopReason}
        assert "cash_in" not in {r.value for r in StopReason}


class TestWhenItOpens:
    def test_carrying_one_opens_the_choice(self) -> None:
        run = carrying()
        assert briefcase_desk.holds(run)
        assert briefcase_desk.can_cash_in(run)

    def test_no_briefcase_no_choice(self) -> None:
        assert not briefcase_desk.holds(make_run(week=WEEK))
        assert not briefcase_desk.can_cash_in(make_run(week=WEEK))

    def test_the_unsigned_cannot_cash_in(self) -> None:
        """**무소속에는 벨트가 없다** (§3-D50) — 단체의 벨트이고 해지가 반납시켰다."""
        loose = carrying().evolve(contract=None)
        assert briefcase_desk.holds(loose), "가방은 그대로 든다"
        assert not briefcase_desk.can_cash_in(loose)
        assert briefcase_desk.target_title(loose) is None

    def test_the_champion_cannot_cash_in_on_himself(self) -> None:
        """이미 그 벨트를 감고 있으면 못 쓴다 — 규칙이 도전을 안 만든다.

        여기서 안 막으면 표식만 서고 아무 일도 없이 가방이 소멸한다.
        """
        run = carrying()
        title = championship.world_title_of(run)
        assert title is not None
        # 든 벨트는 획득 이력에도 있어야 한다 — `CareerRun`의 불변식이다.
        champ = run.evolve(titles_held=frozenset({title}), titles_won=(title,))
        assert not briefcase_desk.can_cash_in(champ)

    def test_deciding_twice_is_refused(self) -> None:
        decided = briefcase_desk.cash_in(carrying())
        assert briefcase_desk.is_pending(decided)
        assert not briefcase_desk.can_cash_in(decided)
        with pytest.raises(CannotCashInError):
            briefcase_desk.cash_in(decided)

    def test_cashing_in_without_one_is_refused(self) -> None:
        with pytest.raises(CannotCashInError):
            briefcase_desk.cash_in(make_run(week=WEEK))


class TestTheClock:
    def test_it_counts_down_from_the_week_you_won_it(self) -> None:
        assert briefcase_desk.weeks_left(carrying()) == rules.BRIEFCASE_WEEKS - 17

    def test_it_never_goes_negative(self) -> None:
        """만료를 부상으로 지나칠 수 있다 — 음수가 뜨면 "이미 늦었다"로 읽힌다."""
        stale = carrying(won_at=WEEK - rules.BRIEFCASE_WEEKS - 30)
        assert briefcase_desk.weeks_left(stale) == 0

    def test_no_briefcase_no_clock(self) -> None:
        assert briefcase_desk.weeks_left(make_run(week=WEEK)) == 0


class TestTheRuleReadsTheMark:
    def test_deciding_only_raises_the_mark(self) -> None:
        """**표식만 세운다.** 경기를 세우는 것은 주차 시뮬의 일이다 (§3-D36)."""
        run = carrying()
        decided = briefcase_desk.cash_in(run)
        assert CASH_IN_PENDING in decided.flags
        # 가방도 벨트도 그대로다 — 아직 아무 일도 안 일어났다.
        assert decided.briefcase_week == run.briefcase_week
        assert decided.titles_held == run.titles_held

    def test_the_title_shot_lands_on_the_next_match_week(self) -> None:
        """정한 뒤 진행하면 **월드 타이틀전이 실제로 선다** (§3-D36).

        규칙이 표식을 읽는지까지 가서 본다 — 도메인만 고치고 규칙이 안 읽으면
        "정했는데 아무 일도 없는" 버튼이 된다.
        """
        run = briefcase_desk.cash_in(carrying())
        target = championship.world_title_of(run)
        for _ in range(30):
            outcome = career_advance.advance(run, max_weeks=4)
            run = outcome.run
            if any(w.title_at_stake is target for w in outcome.reports):
                assert not briefcase_desk.is_pending(run), "쓴 뒤에는 표식이 지워진다"
                assert run.briefcase_week == 0, "가방도 함께 소진된다"
                return
            if not run.is_active:
                break
        pytest.fail("정했는데 타이틀전이 서지 않았다")

    def test_the_target_is_the_belt_the_rule_uses(self) -> None:
        """화면이 가리키는 벨트와 규칙이 거는 벨트가 **같은 함수에서 나온다.**"""
        run = carrying()
        assert briefcase_desk.target_title(run) == championship.world_title_of(run)
