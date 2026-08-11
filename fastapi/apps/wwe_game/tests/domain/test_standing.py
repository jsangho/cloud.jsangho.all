"""평판은 상이 아니라 문턱이다 (하네스 §3-D42).

`backstage`가 하던 일은 **방출 판정 하나**였다 — 26 아래로 내려가면 잘린다. 그
위에서는 92든 46이든 커리어가 똑같이 굴러갔다. 라커룸 평판·부커와의 관계·정치가
전부 그 숫자 하나에 눌려 있었다.
"""

from __future__ import annotations

import pytest
from _helpers import make_run  # noqa: I001
from wwe_game.domain.constants import career_rules as rules
from wwe_game.domain.services.championship import title_shot_chance
from wwe_game.domain.services.week_simulation import week_kind_of
from wwe_game.domain.value_objects.week_report import WeekKind
from wwe_game.domain.value_objects.wrestler_stats import WrestlerStats


class TestGoodStandingBuysNothing:
    """**상을 주지 않는다.** `safe` 플레이는 평판이 92까지 오르는데, 거기에 배수를
    얹으면 이미 잘 풀린 커리어만 더 잘 풀린다 — §3-D41에서 프로모 인기도를 고정으로
    줬다가 경제가 무너진 것과 같은 모양이다.
    """

    @pytest.mark.parametrize("standing", [rules.PUSH_FLOOR, 60, 80, 100])
    def test_above_the_floor_nothing_changes(self, standing: int) -> None:
        assert rules.push_factor(standing) == 1.0

    def test_a_saint_gets_the_same_shots_as_an_ordinary_pro(self) -> None:
        assert title_shot_chance(60, standing=100) == title_shot_chance(
            60, standing=rules.PUSH_FLOOR
        )


class TestBeingDislikedTakesThingsAway:
    def test_opportunity_falls_below_the_floor(self) -> None:
        assert (
            rules.push_factor(0)
            < rules.push_factor(20)
            < rules.push_factor(rules.PUSH_FLOOR - 1)
            < 1.0
        )

    def test_it_never_reaches_zero(self) -> None:
        """**바닥이 0이면 방출 규칙이 무의미해진다** — 아무것도 못 하니 회복도 없다."""
        assert rules.push_factor(0) >= rules.PUSH_MIN_FACTOR > 0.0

    def test_a_hated_wrestler_gets_fewer_title_shots(self) -> None:
        assert title_shot_chance(60, standing=10) < title_shot_chance(60, standing=90)

    def test_a_hated_wrestler_wrestles_less_often(self) -> None:
        """**카드에 자리를 받는 것도 부커의 결정이다.** 미움받으면 링에 덜 선다."""
        liked = _match_weeks(standing=90)
        hated = _match_weeks(standing=5)
        assert hated < liked

    def test_the_release_floor_is_below_the_push_floor(self) -> None:
        """기회가 줄기 **시작한 뒤에** 방출이 온다 — 순서가 뒤집히면 예고가 없다."""
        assert rules.RELEASE_BACKSTAGE_FLOOR < rules.PUSH_FLOOR


def _match_weeks(*, standing: int) -> int:
    """80주 중 경기가 잡히는 주차 수. 대회 주차는 평판과 무관하므로 제외한다."""
    run = make_run(seed=31, stats=WrestlerStats(backstage=standing))
    return sum(
        1
        for week in range(100, 180)
        if week_kind_of(run.evolve(week=week)) is WeekKind.WEEKLY_SHOW
    )
