"""장기 부상이면 벨트를 반납한다 (하네스 §3-D40).

**30주를 결장하면서 벨트를 들고 있었다.** 아무 방어전도 안 하면서. 실제 단체는
챔피언이 길게 빠지면 자리를 비운다 — 벨트는 보관물이 아니라 매주 방어해야 하는
자리이기 때문이다.
"""

from __future__ import annotations

import pytest
from _helpers import make_run  # noqa: I001
from wwe_game.domain.constants import career_rules as rules
from wwe_game.domain.services.week_simulation import apply_week
from wwe_game.domain.value_objects.condition import InjuryGrade
from wwe_game.domain.value_objects.title import Brand, Title
from wwe_game.domain.value_objects.week_report import WeekKind, WeekReport

BELT = Title.INTERCONTINENTAL_CHAMPIONSHIP
TAG = Title.WORLD_TAG_TEAM_CHAMPIONSHIP


def champion(*titles: Title):
    return make_run(brand=Brand.RAW, week=400).evolve(
        titles_held=frozenset(titles), titles_won=titles
    )


def hurt(run, weeks: int) -> WeekReport:
    return WeekReport(
        week=run.week + 1,
        kind=WeekKind.WEEKLY_SHOW,
        injury=InjuryGrade.SERIOUS if weeks >= 10 else InjuryGrade.MINOR,
        injury_weeks=weeks,
        vacated=(
            tuple(sorted(run.titles_held, key=lambda t: t.value))
            if weeks >= rules.VACATE_AFTER_WEEKS
            else ()
        ),
    )


class TestALongAbsenceEmptiesTheChair:
    def test_a_long_injury_takes_the_belt(self) -> None:
        run = champion(BELT)
        after = apply_week(run, hurt(run, 26))
        assert BELT not in after.titles_held

    def test_a_short_injury_does_not(self) -> None:
        """경상(2~6주)은 몇 주 빠지는 것이지 자리를 비우는 것이 아니다."""
        run = champion(BELT)
        after = apply_week(run, hurt(run, 4))
        assert BELT in after.titles_held

    @pytest.mark.parametrize(
        "weeks", [rules.VACATE_AFTER_WEEKS - 1, rules.VACATE_AFTER_WEEKS]
    )
    def test_the_line_is_weeks_not_grade(self, weeks: int) -> None:
        """**등급이 아니라 주차로 잰다** — 회복 주차를 손봐도 규칙의 뜻이 안 바뀐다."""
        run = champion(BELT)
        after = apply_week(run, hurt(run, weeks))
        assert (BELT in after.titles_held) == (weeks < rules.VACATE_AFTER_WEEKS)

    def test_every_belt_goes(self) -> None:
        run = champion(BELT, TAG)
        after = apply_week(run, hurt(run, 20))
        assert after.titles_held == frozenset()

    def test_the_history_stays(self) -> None:
        """**감았던 것은 감았던 것이다.** 그랜드슬램 진행이 부상으로 되돌아가면 안 된다."""
        run = champion(BELT)
        after = apply_week(run, hurt(run, 26))
        assert BELT in after.titles_won

    def test_a_challenger_without_a_belt_loses_nothing(self) -> None:
        run = make_run(brand=Brand.RAW, week=400)
        after = apply_week(run, hurt(run, 26))
        assert after.titles_held == frozenset()
