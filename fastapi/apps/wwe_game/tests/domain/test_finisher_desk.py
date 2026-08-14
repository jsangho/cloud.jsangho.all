"""피니셔 (하네스 §3-D88).

이 게임에는 피니셔라는 개념 자체가 없었다 — 경기를 끝내는 장면은 나레이션이 그때그때
무브 뱅크에서 뽑았고, 그러니까 *내* 기술이 아니라 그 밤의 기술이었다.

여기서 지키는 것 다섯:

1. **모두 수플렉스에서 시작한다** (2026-08-14 사용자 결정)
2. **첫 분기가 지나야 바꾼다** — 그리고 바꾼 뒤에도 한 분기를 기다린다
3. **두 갈래** — 목록에서 고르거나, 이름을 직접 짓거나
4. **판정에 한 톨도 안 닿는다** — 승패·별점·부상 어느 것도 안 본다
5. **21스타일 전부 피니셔가 있다**
"""

from __future__ import annotations

import pytest
from _helpers import make_run  # noqa: I001  (tests 트리에 __init__.py가 없다)
from wwe_game.domain.constants.career_clock import CAREER_WEEKS
from wwe_game.domain.entities.career_run import CareerRun
from wwe_game.domain.exceptions import (
    CannotChangeFinisherError,
    InvalidFinisherNameError,
)
from wwe_game.domain.services import finisher_desk
from wwe_game.domain.value_objects.finisher import (
    CUSTOM_CODE,
    DEFAULT,
    FAMILY_OF,
    FINISHERS,
    NAME_MAX_LEN,
    custom,
    options_for,
)
from wwe_game.domain.value_objects.wrestler_identity import PlayStyle

QUARTER = finisher_desk.COOLDOWN_WEEKS


def rookie(week: int = 0) -> CareerRun:
    return make_run(week=week)


class TestEveryoneStartsWithASuplex:
    def test_a_fresh_career_uses_the_default(self) -> None:
        """**아직 내 기술이 없다**가 그대로 읽혀야 한다."""
        assert finisher_desk.current(rookie()).name == "수플렉스"

    def test_the_style_does_not_change_the_default(self) -> None:
        """계열의 첫 기술을 기본값으로 두면 데뷔하자마자 자기 색이 있는 셈이 된다."""
        for style in PlayStyle:
            run = make_run().evolve(
                identity=make_run().identity.__class__(
                    name=make_run().identity.name,
                    gender=make_run().identity.gender,
                    country=make_run().identity.country,
                    play_style=style,
                )
            )
            assert finisher_desk.current(run).code == DEFAULT.code

    def test_an_old_save_reads_as_the_default(self) -> None:
        """빈 칸이 곧 기본값이다 — 고르지 않은 것과 못 고른 것을 나누지 않는다."""
        assert finisher_desk.current(rookie().evolve(finisher="")).code == DEFAULT.code


class TestTheFirstQuarter:
    def test_a_rookie_cannot_change_yet(self) -> None:
        """**첫 분기가 지나야 바꾼다** (2026-08-14 사용자 결정)."""
        assert not finisher_desk.can_change(rookie(week=0))
        assert finisher_desk.weeks_until_change(rookie(week=0)) == QUARTER

    def test_the_clock_runs_down_with_the_weeks(self) -> None:
        assert finisher_desk.weeks_until_change(rookie(week=QUARTER - 1)) == 1

    def test_after_a_quarter_it_opens(self) -> None:
        assert finisher_desk.can_change(rookie(week=QUARTER))
        assert finisher_desk.weeks_until_change(rookie(week=QUARTER)) == 0

    def test_changing_starts_the_clock_again(self) -> None:
        """바꾼 뒤에도 한 분기를 기다린다 — 매주 바꾸면 설정 메뉴가 된다."""
        run = rookie(week=QUARTER)
        changed = finisher_desk.pick(run, finisher_desk.options(run)[1].code)
        assert changed.finisher_week == QUARTER
        assert not finisher_desk.can_change(changed)
        assert finisher_desk.weeks_until_change(changed) == QUARTER

    def test_a_closed_career_cannot_change(self) -> None:
        from wwe_game.domain.entities.career_run import EndReason

        closed = rookie(week=QUARTER * 4).ended(EndReason.PLAYER)
        assert not finisher_desk.can_change(closed)


class TestKeepingWhatYouHave:
    """**바꾸는 것만이 선택이 아니다** (2026-08-14 사용자 요청).

    분기마다 자리가 열리므로 화면이 계속 물어보게 되는데, "이대로 간다"도 한 번의
    결정이다 — 다시 묻는 날만 미룬다.
    """

    def test_a_quarter_hold_pushes_the_question(self) -> None:
        run = rookie(week=QUARTER)
        held = finisher_desk.hold(run, finisher_desk.HOLD_QUARTER)
        assert finisher_desk.current(held).code == finisher_desk.current(run).code
        assert finisher_desk.weeks_until_change(held) == QUARTER

    def test_a_year_hold_pushes_it_further(self) -> None:
        held = finisher_desk.hold(rookie(week=QUARTER), finisher_desk.HOLD_YEAR)
        assert finisher_desk.weeks_until_change(held) == finisher_desk.HOLD_YEAR

    def test_forever_never_asks_again(self) -> None:
        """**평생 쓰기** — 커리어 끝 너머라 다시 묻는 날이 오지 않는다."""
        held = finisher_desk.hold(rookie(week=QUARTER), finisher_desk.HOLD_FOREVER)
        assert finisher_desk.is_settled(held)
        assert not finisher_desk.can_change(held)
        # 서른 해가 지나도 그대로다.
        assert not finisher_desk.can_change(held.evolve(week=CAREER_WEEKS - 1))

    def test_holding_does_not_touch_the_finisher(self) -> None:
        run = finisher_desk.pick(rookie(week=QUARTER), finisher_desk.options(rookie())[2].code)
        run = run.evolve(week=QUARTER * 2)
        before = finisher_desk.current(run)
        held = finisher_desk.hold(run, finisher_desk.HOLD_YEAR)
        assert finisher_desk.current(held) == before

    def test_holding_before_the_first_quarter_is_refused(self) -> None:
        with pytest.raises(CannotChangeFinisherError):
            finisher_desk.hold(rookie(week=0), finisher_desk.HOLD_QUARTER)

    def test_changing_resets_to_a_quarter(self) -> None:
        """바꾸면 다시 분기다 — 미뤄 둔 것과 바꾼 것은 다른 결정이다."""
        run = finisher_desk.hold(rookie(week=QUARTER), finisher_desk.HOLD_YEAR)
        run = run.evolve(week=QUARTER + finisher_desk.HOLD_YEAR)
        changed = finisher_desk.pick(run, finisher_desk.options(run)[3].code)
        assert finisher_desk.weeks_until_change(changed) == QUARTER


class TestPickingFromTheList:
    def test_the_list_holds_the_default_and_the_family(self) -> None:
        run = rookie(week=QUARTER)
        options = finisher_desk.options(run)
        assert options[0].code == DEFAULT.code, "지금 쓰는 것이 목록에서 읽혀야 한다"
        family = FINISHERS[FAMILY_OF[run.identity.play_style]]
        assert set(options[1:]) == set(family)

    def test_picking_sets_the_code(self) -> None:
        run = rookie(week=QUARTER)
        target = finisher_desk.options(run)[2]
        changed = finisher_desk.pick(run, target.code)
        assert finisher_desk.current(changed).code == target.code
        assert changed.finisher_name == "", "목록에서 고르면 이름 칸은 비운다"

    def test_a_code_outside_the_family_is_refused(self) -> None:
        run = rookie(week=QUARTER)
        outsider = next(
            f
            for pool in FINISHERS.values()
            for f in pool
            if f not in options_for(run.identity.play_style)
        )
        with pytest.raises(CannotChangeFinisherError):
            finisher_desk.pick(run, outsider.code)

    def test_picking_what_you_already_use_is_refused(self) -> None:
        """쿨다운만 태우고 아무것도 안 바뀐다."""
        with pytest.raises(CannotChangeFinisherError):
            finisher_desk.pick(rookie(week=QUARTER), DEFAULT.code)


class TestNamingYourOwn:
    def test_a_name_becomes_the_finisher(self) -> None:
        changed = finisher_desk.name_it(rookie(week=QUARTER), "장상호 드라이버")
        now = finisher_desk.current(changed)
        assert now.name == "장상호 드라이버"
        assert now.code == CUSTOM_CODE

    def test_it_survives_a_reload(self) -> None:
        """이름 칸에 그대로 담긴다 — 코드 칸과 나눠 둔 이유가 이것이다."""
        changed = finisher_desk.name_it(rookie(week=QUARTER), "붉은 낙인")
        assert changed.finisher_name == "붉은 낙인"
        assert finisher_desk.current(changed).name == "붉은 낙인"

    @pytest.mark.parametrize("bad", ["", " ", "가", "다" * (NAME_MAX_LEN + 1)])
    def test_the_length_rule_matches_the_ring_name(self, bad: str) -> None:
        with pytest.raises(InvalidFinisherNameError):
            custom(bad)

    def test_control_characters_are_refused(self) -> None:
        """서술 한 줄이 두 줄로 깨진다 (§3-D12와 같은 이유)."""
        with pytest.raises(InvalidFinisherNameError):
            custom("한 줄\n두 줄")

    def test_the_name_is_trimmed(self) -> None:
        assert custom("  마무리  ").name == "마무리"

    def test_naming_the_same_thing_is_refused(self) -> None:
        run = finisher_desk.name_it(rookie(week=QUARTER), "붉은 낙인")
        run = run.evolve(week=QUARTER * 2)
        with pytest.raises(CannotChangeFinisherError):
            finisher_desk.name_it(run, "붉은 낙인")

    def test_a_tampered_save_falls_back_to_the_default(self) -> None:
        """손댄 세이브가 규칙 밖 이름을 들고 와도 화면이 죽지 않는다."""
        broken = rookie().evolve(finisher=CUSTOM_CODE, finisher_name="줄\n바꿈")
        assert finisher_desk.current(broken).code == DEFAULT.code


class TestItNeverTouchesTheRules:
    def test_every_style_has_a_family(self) -> None:
        """**21종을 하나도 빠뜨리지 않는다** — 빠지면 그 스타일은 피니셔가 없다."""
        assert set(FAMILY_OF) == set(PlayStyle)

    def test_every_family_has_enough_to_choose_from(self) -> None:
        for family, pool in FINISHERS.items():
            assert len(pool) >= 5, f"{family}: 고를 것이 모자란다"
            assert len({f.code for f in pool}) == len(pool)

    def test_no_finisher_carries_a_number(self) -> None:
        """**수치가 없다** — 판정에 닿지 않기 때문이다 (§3-D29·§11-14)."""
        fields = set(DEFAULT.__dataclass_fields__)
        assert fields == {"code", "name", "blurb"}

    def test_changing_moves_nothing_but_the_finisher(self) -> None:
        """승패·별점·부상 어느 것도 안 본다 — 바뀌는 것은 세 칸뿐이다."""
        run = rookie(week=QUARTER)
        changed = finisher_desk.pick(run, finisher_desk.options(run)[3].code)
        assert changed.stats == run.stats
        assert changed.condition == run.condition
        assert changed.money == run.money
        assert changed.week == run.week
