"""부상 부위 — 무릎과 목은 같은 부상이 아니다 (하네스 §3-D43).

부상은 **등급 셋**이 전부였다. 하이플라이어가 착지를 잘못한 것과 파워하우스가 허리를
삐끗한 것이 같은 사건이었고, 로그도 같은 문장을 썼다.
"""

from __future__ import annotations

import pytest
from _helpers import make_run  # noqa: I001
from wwe_game.domain.exceptions import InvalidConditionError
from wwe_game.domain.services.seeded_roll import SeededRoll
from wwe_game.domain.services.week_simulation import apply_week
from wwe_game.domain.value_objects import body_part
from wwe_game.domain.value_objects.body_part import PARTS, BodyPart, parts_for
from wwe_game.domain.value_objects.condition import Condition, InjuryGrade
from wwe_game.domain.value_objects.week_report import WeekKind, WeekReport
from wwe_game.domain.value_objects.wrestler_identity import PlayStyle


class TestThePartDecidesHowLong:
    def test_a_neck_keeps_you_out_longest(self) -> None:
        longest = max(PARTS, key=lambda p: PARTS[p].recovery)
        assert longest is BodyPart.NECK

    def test_ribs_are_the_quickest(self) -> None:
        quickest = min(PARTS, key=lambda p: PARTS[p].recovery)
        assert quickest is BodyPart.RIBS

    def test_the_second_time_is_worse(self) -> None:
        """**두 번째는 더 오래 간다** — 몸이 기억한다는 말의 절반이다."""
        first = body_part.recovery_factor(BodyPart.KNEE, again=False)
        second = body_part.recovery_factor(BodyPart.KNEE, again=True)
        assert second > first


class TestStyleChoosesWhereYouBreak:
    @pytest.mark.parametrize(
        ("style", "expected"),
        [
            (PlayStyle.HIGH_FLYER, BodyPart.KNEE),
            (PlayStyle.POWERHOUSE, BodyPart.BACK),
            (PlayStyle.HARDCORE, BodyPart.CONCUSSION),
            (PlayStyle.SUBMISSIONS, BodyPart.ARM),
        ],
    )
    def test_each_style_breaks_where_it_works(
        self, style: PlayStyle, expected: BodyPart
    ) -> None:
        assert expected in parts_for(style)

    def test_a_style_without_a_list_can_break_anywhere(self) -> None:
        """쇼맨처럼 몸 쓰는 방식이 한쪽으로 안 쏠리는 유형은 전부가 후보다."""
        assert set(parts_for(PlayStyle.SHOWMAN)) == set(BodyPart)


class TestTheBodyRemembers:
    @staticmethod
    def hurt(run, part: BodyPart, weeks: int = 12):
        report = WeekReport(
            week=run.week + 1,
            kind=WeekKind.WEEKLY_SHOW,
            injury=InjuryGrade.SERIOUS,
            injury_weeks=weeks,
            injury_part=part,
        )
        return apply_week(run, report)

    def test_an_injury_is_written_into_the_history(self) -> None:
        after = self.hurt(make_run(week=200), BodyPart.KNEE)
        assert BodyPart.KNEE.value in after.injured_parts
        assert after.condition.part is BodyPart.KNEE

    def test_the_history_outlives_the_injury(self) -> None:
        """**낫는 것은 부상이지 이력이 아니다.** 이력이 지워지면 재발이 성립하지 않는다."""
        after = self.hurt(make_run(week=200), BodyPart.KNEE, weeks=1)
        healed = after.evolve(condition=after.condition.recover(5))
        assert not healed.condition.is_injured
        assert healed.condition.part is None
        assert BodyPart.KNEE.value in healed.injured_parts

    def test_history_beats_style_when_it_fires(self) -> None:
        """이력이 있으면 스타일 목록보다 앞선다 — 그래야 같은 곳을 또 다친다."""
        run = make_run(week=200, style=PlayStyle.SUBMISSIONS).evolve(
            injured_parts=frozenset({BodyPart.NECK.value})
        )
        assert BodyPart.NECK not in parts_for(PlayStyle.SUBMISSIONS)
        drawn = {_draw(run, seed) for seed in range(40)}
        assert BodyPart.NECK in drawn, "이력이 있는데 한 번도 재발하지 않았다"


class TestHealingClearsThePart:
    def test_being_healthy_with_a_part_is_impossible(self) -> None:
        """회복이 부위를 안 지우면 "건강한데 무릎이 나간" 상태가 남는다."""
        with pytest.raises(InvalidConditionError):
            Condition(grade=InjuryGrade.HEALTHY, weeks_left=0, part=BodyPart.KNEE)

    def test_recovering_wipes_it(self) -> None:
        hurt = Condition(grade=InjuryGrade.MINOR, weeks_left=2, part=BodyPart.ANKLE)
        assert hurt.recover(2).part is None


def _draw(run, seed: int) -> BodyPart:
    from wwe_game.domain.services.week_simulation import _draw_body_part

    return _draw_body_part(run, SeededRoll(seed, 1, "injury"))
