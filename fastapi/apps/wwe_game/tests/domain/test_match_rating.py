"""경기 별점 (하네스 §3-D56).

이 파일이 잠그는 것은 둘이다 — **별점은 판정에 닿지 않는다**는 것과, **별 다섯이
흔해지지 않는다**는 것. 두 번째는 실제로 한 번 깨진 적이 있다(첫 조율에서 별 다섯이
39.6%였다).
"""

from __future__ import annotations

import statistics

import pytest
from wwe_game.domain.constants.roster import RivalTier
from wwe_game.domain.services import match_rating

SEED = 7777


def _rate(**kwargs: object) -> float:
    base: dict[str, object] = {"in_ring": 70, "rival_tier": RivalTier.MIDCARD}
    base.update(kwargs)
    return match_rating.rate(SEED, 100, **base)  # type: ignore[arg-type]


class TestItIsAlwaysTheSameMatch:
    def test_the_same_night_gets_the_same_stars(self) -> None:
        assert _rate() == _rate()

    def test_another_week_is_another_match(self) -> None:
        weeks = {match_rating.rate(SEED, w, in_ring=70) for w in range(100, 140)}
        assert len(weeks) > 1, "주차가 달라도 별점이 같다 — 굴림이 안 돌고 있다"

    def test_matches_on_one_night_differ(self) -> None:
        # `salt`가 없으면 한 밤의 모든 경기가 똑같이 흔들린다.
        first = match_rating.rate(SEED, 100, in_ring=70, salt="a")
        second = match_rating.rate(SEED, 100, in_ring=70, salt="b")
        assert first != second


class TestTheScaleMeansSomething:
    def test_it_lands_on_quarters(self) -> None:
        for week in range(1, 200):
            value = match_rating.rate(SEED, week, in_ring=70)
            assert round(value / match_rating.STEP) * match_rating.STEP == value

    def test_it_stays_in_range(self) -> None:
        for week in range(1, 400):
            for ring in (0, 50, 100):
                value = match_rating.rate(SEED, week, in_ring=ring, has_title=True)
                assert 0.0 <= value <= match_rating.MAX_STARS

    def test_five_is_possible(self) -> None:
        """**다섯을 넘길 수 있다** (2026-08-12 사용자 요청)."""
        top = max(
            match_rating.rate(
                SEED,
                week,
                in_ring=95,
                rival_tier=RivalTier.MAIN_EVENT,
                stage="major",
                has_title=True,
                has_stipulation=True,
            )
            for week in range(1, 1561)
        )
        assert top > 5.0, f"30년을 굴려도 별 다섯을 못 넘었다: {top}"

    def test_five_stays_rare(self) -> None:
        """별 다섯이 흔하면 별점은 아무 말도 하지 않는다."""
        rolled = [
            match_rating.rate(
                SEED,
                week,
                in_ring=75,
                rival_tier=RivalTier.MAIN_EVENT,
                stage="ple",
                has_title=True,
            )
            for week in range(1, 1561)
        ]
        share = sum(1 for value in rolled if value >= 5.0) / len(rolled)
        assert share < 0.05, f"별 다섯이 {share:.1%}나 된다"

    def test_an_ordinary_match_sits_in_the_middle(self) -> None:
        rolled = [match_rating.rate(SEED, week, in_ring=60) for week in range(1, 1561)]
        assert 2.0 <= statistics.mean(rolled) <= 3.5


class TestBetterConditionsRateHigher:
    @pytest.mark.parametrize(
        ("field", "value"),
        [("has_title", True), ("has_stipulation", True), ("stage", "major")],
    )
    def test_each_bonus_lifts_the_average(self, field: str, value: object) -> None:
        weeks = range(1, 400)
        plain = statistics.mean(match_rating.rate(SEED, w, in_ring=70) for w in weeks)
        lifted = statistics.mean(
            match_rating.rate(SEED, w, in_ring=70, **{field: value})  # type: ignore[arg-type]
            for w in weeks
        )
        assert lifted > plain

    def test_a_better_wrestler_rates_higher(self) -> None:
        weeks = range(1, 400)
        low = statistics.mean(match_rating.rate(SEED, w, in_ring=40) for w in weeks)
        high = statistics.mean(match_rating.rate(SEED, w, in_ring=90) for w in weeks)
        assert high > low + 0.5

    def test_a_better_rival_rates_higher(self) -> None:
        weeks = range(1, 400)
        low = statistics.mean(
            match_rating.rate(SEED, w, in_ring=70, rival_tier=RivalTier.PROSPECT)
            for w in weeks
        )
        high = statistics.mean(
            match_rating.rate(SEED, w, in_ring=70, rival_tier=RivalTier.MAIN_EVENT)
            for w in weeks
        )
        assert high > low
