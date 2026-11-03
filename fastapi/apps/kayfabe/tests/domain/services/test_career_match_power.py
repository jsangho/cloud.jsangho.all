"""경기력 분해(`power_parts`). **나눈 뒤에도 합과 승률이 비트 단위로 같다.**

`_REFERENCE` 는 분해 전 `_power` 의 식을 그대로 옮긴 것이다. 근사 비교(`approx`)를
쓰지 않는다 — 끝자리 하나가 다르면 경계에 걸린 뽑기(`roll < p`)가 뒤집힐 수 있다.
"""

from __future__ import annotations

import itertools

from kayfabe.domain.services import career_match as match
from kayfabe.domain.services.career_world import Ability, Wrestler


def _reference(w: Wrestler) -> float:
    """분해 전 식(ho=ca13b58 `career_match._power`)."""
    skill = w.ability.in_ring / 100.0
    draw = w.popularity / 100.0
    cond = w.condition / 100.0
    stam = w.ability.stamina / 100.0
    return skill * 0.5 + draw * 0.25 + (cond * 0.6 + stam * 0.4) * 0.25


def _grid() -> list[Wrestler]:
    values = (1, 7, 33, 50, 64, 99, 100)
    return [
        Wrestler(
            name=f"w{i}",
            style="파워",
            popularity=pop,
            condition=cond,
            ability=Ability(in_ring=ring, mic=40, stamina=stam, resilience=70),
        )
        for i, (ring, pop, cond, stam) in enumerate(itertools.product(values, repeat=4))
    ]


def test_parts_sum_to_reference_exactly() -> None:
    for w in _grid():
        parts = match.power_parts(w)
        assert parts.total == _reference(w)
        assert match._power(w) == _reference(w)


def test_parts_are_the_weighted_terms() -> None:
    w = Wrestler(
        name="x",
        style="파워",
        popularity=60,
        condition=80,
        ability=Ability(in_ring=70, mic=40, stamina=50, resilience=70),
    )

    parts = match.power_parts(w)

    assert parts.skill == 0.70 * 0.5
    assert parts.draw == 0.60 * 0.25
    assert parts.body == (0.80 * 0.6 + 0.50 * 0.4) * 0.25


def test_win_probability_unchanged() -> None:
    """승률 공식은 `_power` 를 그대로 쓴다 — 기준 식으로 다시 계산해도 같은 값."""
    grid = _grid()[::37]
    for a, b in itertools.product(grid, repeat=2):
        for title, challenger in ((False, None), (True, a.name), (True, b.name)):
            expected = 0.5 + (_reference(a) - _reference(b)) * 0.9
            if title and challenger is not None:
                expected += -0.12 if challenger == a.name else 0.12
            expected = max(match.FLOOR, min(match.CEIL, expected))

            got = match.win_probability(a, b, title_match=title, challenger=challenger)

            assert got == expected
