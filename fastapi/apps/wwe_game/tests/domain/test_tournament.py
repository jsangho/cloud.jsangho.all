"""킹 앤 퀸 오브 더 링 토너먼트 — 한 주에 안 끝나는 유일한 형식 (하네스 §3-D33).

**결승이 서는 밤이 바뀌었다** (§3-D71, 2026-08-12): 사용자가 가져온 목록에 킹 앤 퀸
대회가 없어서, 결승은 나이트 오브 챔피언스로 옮겼다. 예선 둘은 그대로 앞 두 주다.

다른 경기는 그 주에 결판이 나므로 리포트 하나로 끝난다. 토너먼트만 **지난주에
이겼는가**를 다음 주가 알아야 하고, 그래서 세이브에 칸이 하나 생겼다.
"""

from __future__ import annotations

import pytest
from _helpers import make_run  # noqa: I001
from wwe_game.domain.constants import career_rules as rules
from wwe_game.domain.constants.ple_calendar import NIGHT_OF_CHAMPIONS, calendar_for
from wwe_game.domain.services.week_simulation import (
    apply_week,
    simulate_week,
    tournament_round_at,
    week_kind_of,
)
from wwe_game.domain.value_objects.match_kind import QUALIFIER_KINDS
from wwe_game.domain.value_objects.title import Brand
from wwe_game.domain.value_objects.week_report import OutcomeKind, WeekKind, WeekReport
from wwe_game.domain.value_objects.wrestler_identity import Gender

FINAL_WEEK = next(
    s.week_of_year
    for s in calendar_for(Brand.RAW).shows
    if s.name == NIGHT_OF_CHAMPIONS
)
YEAR = 52 * 6
"""6년차 — 메인 로스터에 올라와 있을 만한 시점."""


def at(round_number: int) -> int:
    """그 회전이 열리는 커리어 주차."""
    return YEAR + FINAL_WEEK - (rules.TOURNAMENT_ROUNDS - round_number)


class TestTheBracketSpansWeeks:
    def test_three_rounds_before_and_at_the_show(self) -> None:
        run = make_run(brand=Brand.RAW)
        assert [tournament_round_at(run, at(r)) for r in (1, 2, 3)] == [1, 2, 3]

    def test_the_final_is_the_show_night(self) -> None:
        assert at(rules.TOURNAMENT_ROUNDS) % 52 == FINAL_WEEK % 52

    def test_ordinary_weeks_are_not_tournament_weeks(self) -> None:
        run = make_run(brand=Brand.RAW)
        assert tournament_round_at(run, at(1) - 1) == 0
        assert tournament_round_at(run, at(3) + 1) == 0

    def test_nxt_has_no_such_tournament(self) -> None:
        """육성 브랜드 달력에 없는 이름이라 자동으로 0이 된다."""
        run = make_run(brand=Brand.NXT)
        assert all(tournament_round_at(run, at(r)) == 0 for r in (1, 2, 3))

    def test_a_qualifier_week_always_has_a_match(self) -> None:
        """**프로모로 넘어가면 대진표가 그 주에 멈춘다** — 결승에 올라간 사람이 없어진다."""
        run = make_run(brand=Brand.RAW, week=at(1) - 1)
        assert week_kind_of(run) is WeekKind.WEEKLY_SHOW


class TestAdvancingAndFalling:
    @staticmethod
    def entered(round_number: int, won_so_far: int):
        return make_run(brand=Brand.RAW, week=at(round_number) - 1).evolve(
            tournament_round=won_so_far
        )

    def test_the_first_round_is_open_to_everyone(self) -> None:
        report = simulate_week(self.entered(1, 0))
        assert report.tournament_round == 1
        assert report.match_kind in QUALIFIER_KINDS

    def test_winning_carries_you_to_the_next_week(self) -> None:
        run = self.entered(1, 0)
        report = WeekReport(
            week=run.week + 1,
            kind=WeekKind.WEEKLY_SHOW,
            result=OutcomeKind.WIN,
            tournament_round=1,
        )
        assert apply_week(run, report).tournament_round == 1

    def test_losing_drops_you_from_the_bracket(self) -> None:
        run = self.entered(2, 1)
        report = WeekReport(
            week=run.week + 1,
            kind=WeekKind.WEEKLY_SHOW,
            result=OutcomeKind.LOSS,
            tournament_round=2,
        )
        assert apply_week(run, report).tournament_round == 0

    def test_you_cannot_skip_a_round(self) -> None:
        """준결승 주차에 1회전을 안 이겼으면 그냥 평범한 밤이다."""
        assert simulate_week(self.entered(2, 0)).tournament_round == 0

    def test_the_bracket_resets_after_the_show(self) -> None:
        """**해마다 새로 연다.** 작년의 진출이 남으면 이듬해에 결승부터 시작한다."""
        run = self.entered(3, 2)
        report = WeekReport(
            week=run.week + 1, kind=WeekKind.PLE, result=OutcomeKind.LOSS
        )
        assert apply_week(run, report).tournament_round == 0


class TestTheCrown:
    @pytest.mark.parametrize(
        ("gender", "code"),
        [(Gender.MALE, "king_of_the_ring"), (Gender.FEMALE, "queen_of_the_ring")],
    )
    def test_winning_the_final_earns_a_trophy(self, gender: Gender, code: str) -> None:
        from dataclasses import replace

        run = make_run(brand=Brand.RAW, week=at(3) - 1).evolve(tournament_round=2)
        run = run.evolve(identity=replace(run.identity, gender=gender))
        report = WeekReport(
            week=run.week + 1,
            kind=WeekKind.PLE,
            result=OutcomeKind.WIN,
            tournament_round=rules.TOURNAMENT_ROUNDS,
        )
        after = apply_week(run, report)
        assert [t.code for t in after.trophies] == [code]

    def test_losing_the_final_earns_nothing(self) -> None:
        run = make_run(brand=Brand.RAW, week=at(3) - 1).evolve(tournament_round=2)
        report = WeekReport(
            week=run.week + 1,
            kind=WeekKind.PLE,
            result=OutcomeKind.LOSS,
            tournament_round=rules.TOURNAMENT_ROUNDS,
        )
        assert apply_week(run, report).trophies == ()

    def test_the_crown_pays_popularity(self) -> None:
        run = make_run(brand=Brand.RAW, week=at(3) - 1).evolve(tournament_round=2)
        report = simulate_week(run)
        if report.result is OutcomeKind.WIN:
            assert (
                report.stat_delta.get("popularity", 0)
                >= rules.TOURNAMENT_WIN_POPULARITY
            )
