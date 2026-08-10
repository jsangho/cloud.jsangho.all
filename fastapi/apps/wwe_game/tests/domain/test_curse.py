"""댄하우젠의 저주 — 판정을 건너뛰는 유일한 표식 (2026-08-10 사용자 지시 4번)."""

from __future__ import annotations

from _helpers import make_run  # noqa: I001  (tests 트리에 __init__.py가 없다)
from wwe_game.domain.constants.career_flags import CURSED
from wwe_game.domain.constants.event_deck import DECK
from wwe_game.domain.services.week_simulation import apply_week, simulate_week
from wwe_game.domain.value_objects.week_report import OutcomeKind, WeekKind


def _first_match(run, limit: int = 60):
    """경기가 있는 첫 주차의 리포트. 프로모·결장 주차는 건너뛴다."""
    for _ in range(limit):
        report = simulate_week(run)
        if report.result is not None:
            return run, report
        run = apply_week(run, report)
    raise AssertionError(f"{limit}주 안에 경기가 없었다")


class TestTheCurseAlwaysWins:
    def test_a_cursed_match_is_always_a_loss(self) -> None:
        # 확률로 옮기면 100번에 몇 번은 이기게 되고, 그러면 저주가 아니라 페널티다.
        for seed in range(30):
            run = make_run(seed=seed).evolve(flags=frozenset({CURSED}))
            _, report = _first_match(run)
            assert report.result is OutcomeKind.LOSS
            assert report.cursed is True

    def test_the_same_week_would_have_been_won_without_it(self) -> None:
        # 저주가 없었다면 이겼을 주차가 하나라도 있어야 규칙이 실제로 일하는 것이다.
        flipped = 0
        for seed in range(30):
            clean = make_run(seed=seed)
            _, plain = _first_match(clean)
            _, cursed = _first_match(clean.evolve(flags=frozenset({CURSED})))
            if plain.result is OutcomeKind.WIN and cursed.result is OutcomeKind.LOSS:
                flipped += 1
        assert flipped > 0

    def test_it_is_spent_on_one_match(self) -> None:
        run = make_run(seed=7).evolve(flags=frozenset({CURSED}))
        run, report = _first_match(run)
        after = apply_week(run, report)
        assert CURSED not in after.flags

    def test_a_quiet_week_does_not_spend_it(self) -> None:
        # 저주를 받아 놓고 쉬면 복귀전이 대가를 치른다.
        run = make_run(seed=3).evolve(flags=frozenset({CURSED}))
        for _ in range(60):
            report = simulate_week(run)
            if report.result is not None:
                break
            run = apply_week(run, report)
            assert CURSED in run.flags


class TestTheDeckCanCastIt:
    def test_a_card_actually_sets_the_curse(self) -> None:
        casters = [
            card.code
            for card in DECK
            for choice in card.choices
            if CURSED in choice.flags
        ]
        assert casters, "저주를 거는 카드가 없다"

    def test_the_curse_never_lands_on_a_quiet_week_report(self) -> None:
        # 경기가 없는 주차는 `cursed`가 서면 안 된다 — 서술이 진 경기를 지어낸다.
        run = make_run(seed=11).evolve(flags=frozenset({CURSED}))
        for _ in range(40):
            report = simulate_week(run)
            if report.kind in (WeekKind.PROMO, WeekKind.OFF):
                assert report.cursed is False
            if report.result is not None:
                break
            run = apply_week(run, report)
