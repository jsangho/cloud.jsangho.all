"""마이크웍이 결과를 만든다 (하네스 §3-D41).

그전까지 이 스탯은 종합점수 가중치 0.10과 베테랑 보정이 전부여서, **마이크웍 90인
선수와 20인 선수의 프로모 주차가 똑같았다** — 커리어의 38%가 그 주차인데도.
"""

from __future__ import annotations

import pytest
from _helpers import make_run  # noqa: I001
from wwe_game.domain.constants import career_rules as rules
from wwe_game.domain.services import rivalry_engine
from wwe_game.domain.services.week_simulation import (
    apply_week,
    promo_hit_chance,
    simulate_week,
)
from wwe_game.domain.value_objects.week_report import WeekKind, WeekReport
from wwe_game.domain.value_objects.wrestler_stats import WrestlerStats


class TestTheMicDecidesThePromo:
    def test_a_better_talker_lands_more_often(self) -> None:
        assert promo_hit_chance(20) < promo_hit_chance(55) < promo_hit_chance(90)

    def test_even_a_poor_talker_lands_sometimes(self) -> None:
        """**바닥을 0으로 두지 않는다** — 말이 서툴러도 관중이 반응하는 밤은 있다."""
        assert promo_hit_chance(0) > 0.0

    def test_the_best_talker_is_not_guaranteed(self) -> None:
        assert promo_hit_chance(100) < 1.0

    @pytest.mark.parametrize("mic", [10, 50, 95])
    def test_a_promo_week_always_reports_a_verdict(self, mic: int) -> None:
        """프로모 주차는 성패가 **반드시 정해진다** — None이면 화면이 말할 것이 없다."""
        run = make_run(seed=7, week=200, stats=WrestlerStats(mic_work=mic))
        report = _first_promo(run)
        assert report.promo_hit is not None

    def test_a_match_week_has_no_promo_verdict(self) -> None:
        run = make_run(seed=7, week=200)
        for step in range(60):
            report = simulate_week(run.evolve(week=200 + step))
            if report.kind is not WeekKind.PROMO:
                assert report.promo_hit is None
                return
        pytest.fail("경기 주차를 못 찾았다")


class TestWhatALandedPromoBuys:
    def test_a_landed_promo_heats_the_feud_far_more(self) -> None:
        """**말을 잘하는 선수가 이야기를 빨리 만든다** — 고정 7이던 시절의 반대다."""
        assert rivalry_engine.HEAT_PER_PROMO > rivalry_engine.HEAT_PER_PROMO_MISS * 3

    def test_the_popularity_goes_through_the_usual_path(self) -> None:
        """**고정값으로 주면 경제가 무너진다** (§3-D41).

        먹힌 밤마다 인기도 +2를 고정으로 줬더니 평균 인기도가 59.5 → 93.9로 폭발하고
        완주율이 60% → 30%로 무너졌다. 이 경제의 모든 상승은 확률 × 체감을 지난다.
        """
        assert rules.PROMO_HIT_POPULARITY_CHANCE < rules.POPULARITY_GAIN_CHANCE["win"]

    def test_a_landed_promo_never_pays_more_than_one(self) -> None:
        run = make_run(seed=7, week=200, stats=WrestlerStats(mic_work=95))
        report = _first_promo(run)
        assert report.stat_delta.get("popularity", 0) <= 1


class TestTheHeatFollowsTheVerdict:
    @staticmethod
    def heat_after(hit: bool) -> int:
        run = make_run(seed=3, week=200, stats=WrestlerStats(popularity=50)).evolve(
            rivalries=(
                rivalry_engine.Rivalry(
                    "행크 워커", rivalry_engine.RivalryStage.HEATED, 40, 100
                ),
            )
        )
        report = WeekReport(week=run.week + 1, kind=WeekKind.PROMO, promo_hit=hit)
        return apply_week(run, report).rivalries[0].heat

    def test_landing_builds_the_feud_faster(self) -> None:
        assert self.heat_after(hit=True) > self.heat_after(hit=False)


def _first_promo(run) -> WeekReport:
    for step in range(80):
        report = simulate_week(run.evolve(week=run.week + step))
        if report.kind is WeekKind.PROMO:
            return report
    raise AssertionError("프로모 주차를 못 찾았다")
