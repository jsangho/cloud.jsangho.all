"""장난감 경기 시뮬레이터 (`domain/services/match_sim`).

**이 파일이 붙드는 것은 "재미"가 아니라 계약 넷이다.**

1. **결정론** — 같은 쌍이면 항상 같은 승자. `hash()` 를 쓰면 재기동마다 달라진다.
2. **대칭** — 인수 순서가 승자를 바꾸지 않는다. 처음 구현이 여기서 틀렸다.
3. **경계** — 확률이 `0.15`~`0.85` 를 벗어나지 않는다(업셋이 항상 남는다).
4. **공식이 조용히 세지지 않는다** — 가중치 상수를 바꾸면 이 파일이 깨진다.

순수 함수라 DB도 난수 시드 주입도 필요 없다.
"""

from __future__ import annotations

import math

import pytest

from kayfabe.domain.services.match_sim import (
    AGE_SPREAD,
    PEAK_AGE,
    UPSET_DAMPING,
    Contender,
    contender_score,
    simulate,
)

_VET = Contender(name="Roman Reigns", titles=12, age=41)
_ROOKIE = Contender(name="Brad Baylor", titles=1, age=21)
_NOBODY = Contender(name="Jacob Fatu", titles=0, age=34)


class TestDeterminism:
    def test_same_pair_gives_same_verdict(self) -> None:
        first = simulate(_VET, _ROOKIE)
        second = simulate(_VET, _ROOKIE)
        assert first == second

    def test_roll_does_not_depend_on_process(self) -> None:
        """`sha256` 고정값. 파이썬 `hash()` 였다면 실행마다 달라진다."""
        assert simulate(_VET, _ROOKIE).roll == pytest.approx(0.9347171528, abs=1e-9)

    def test_name_case_and_space_do_not_change_the_roll(self) -> None:
        loud = Contender(name="  ROMAN REIGNS ", titles=12, age=41)
        assert simulate(loud, _ROOKIE).roll == simulate(_VET, _ROOKIE).roll


class TestSymmetry:
    """**처음 구현이 여기서 틀렸다.** 확률은 대칭인데 부등호가 아니어서,
    `roll 0.252` · `p_a 0.547` 일 때 `(a,b)` 는 a 가, `(b,a)` 는 b 가 이겼다."""

    @pytest.mark.parametrize(
        ("a", "b"),
        [(_VET, _ROOKIE), (_VET, _NOBODY), (_ROOKIE, _NOBODY)],
    )
    def test_argument_order_does_not_change_the_winner(
        self, a: Contender, b: Contender
    ) -> None:
        assert simulate(a, b).winner == simulate(b, a).winner

    @pytest.mark.parametrize(
        ("a", "b"),
        [(_VET, _ROOKIE), (_VET, _NOBODY), (_ROOKIE, _NOBODY)],
    )
    def test_probabilities_sum_to_one(self, a: Contender, b: Contender) -> None:
        assert simulate(a, b).probability_a + simulate(b, a).probability_a == (
            pytest.approx(1.0)
        )


class TestBounds:
    def test_upset_is_always_possible(self) -> None:
        """압도적 차이에서도 확률이 `0.85` 를 넘지 않는다 — 100% 는 거짓이다."""
        monster = Contender(name="Monster", titles=500, age=PEAK_AGE)
        nobody = Contender(name="Nobody", titles=0, age=70)
        p = simulate(monster, nobody).probability_a
        assert p < 0.5 + UPSET_DAMPING / 2 + 1e-9
        assert p > 0.5

    def test_equal_contenders_are_a_coin_flip(self) -> None:
        left = Contender(name="Rookie A", titles=0, age=25)
        right = Contender(name="Rookie B", titles=0, age=25)
        assert simulate(left, right).probability_a == pytest.approx(0.5)


class TestScore:
    def test_titles_are_damped(self) -> None:
        """21회가 1회의 21배면 베테랑이 무조건 이긴다. `log1p` 로 누른다."""
        one = contender_score(Contender(name="x", titles=1, age=None))
        many = contender_score(Contender(name="y", titles=21, age=None))
        assert many < one * 21

    def test_titles_are_monotonic(self) -> None:
        scores = [
            contender_score(Contender(name="x", titles=n, age=None))
            for n in (0, 1, 5, 21)
        ]
        assert scores == sorted(scores)

    def test_peak_age_is_the_best_age(self) -> None:
        peak = contender_score(Contender(name="x", titles=3, age=PEAK_AGE))
        young = contender_score(Contender(name="x", titles=3, age=20))
        old = contender_score(Contender(name="x", titles=3, age=40))
        assert peak > young
        assert peak > old

    def test_unknown_age_skips_the_correction(self) -> None:
        """생일을 모르는 선수에게 나이 벌점을 주지 않는다."""
        unknown = contender_score(Contender(name="x", titles=3, age=None))
        peak = contender_score(Contender(name="x", titles=3, age=PEAK_AGE))
        assert unknown == peak

    def test_age_penalty_stays_worth_about_one_title(self) -> None:
        """**공식이 조용히 세지지 않게 박는다.**

        의도는 "정점에서 14년 벗어나면 타이틀 1회 분량" 이다. `AGE_SPREAD` 를
        작게 바꾸면 나이가 커리어를 이기기 시작하고, 그때 이 테스트가 깨진다 —
        처음 `100` 에서 10회 챔피언(41세)이 2회 신인(21세)에게 졌던 그 자리다.
        """
        penalty = math.log1p(1)
        drift = ((PEAK_AGE + 14 - PEAK_AGE) ** 2) / AGE_SPREAD
        assert drift == pytest.approx(penalty, rel=0.1)

    def test_career_beats_youth(self) -> None:
        """10회 챔피언(41세)이 2회 신인(21세)보다 높아야 한다."""
        veteran = contender_score(Contender(name="v", titles=10, age=41))
        rookie = contender_score(Contender(name="r", titles=2, age=21))
        assert veteran > rookie

    def test_negative_titles_are_treated_as_zero(self) -> None:
        assert contender_score(
            Contender(name="x", titles=-5, age=None)
        ) == contender_score(Contender(name="x", titles=0, age=None))
