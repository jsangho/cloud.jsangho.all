"""럼블·챔버 도전권과 MITB 가방 (하네스 §3-D36).

**셋 다 1회용이다** (2026-08-11 사용자 확인). 도전권은 그해 레슬매니아에서 쓰고,
가방은 1년 안에 쓴다. 여기서 잠그는 것은 그 소멸이다 — 권리가 안 사라지면 30년짜리
커리어에서 무한정 쌓인다.
"""

from __future__ import annotations

import pytest
from _helpers import make_run  # noqa: I001
from wwe_game.domain.constants import career_rules as rules
from wwe_game.domain.constants.career_flags import CASH_IN_PENDING
from wwe_game.domain.constants.ple_calendar import MITB, WRESTLEMANIA, calendar_for
from wwe_game.domain.services.week_simulation import apply_week, simulate_week
from wwe_game.domain.value_objects.match_kind import MatchKind
from wwe_game.domain.value_objects.title import TITLES, Brand, Title, TitleTier
from wwe_game.domain.value_objects.week_report import (
    OutcomeKind,
    TitleShotSource,
    WeekKind,
    WeekReport,
)
from wwe_game.domain.value_objects.wrestler_stats import WrestlerStats

CALENDAR = calendar_for(Brand.RAW)


def week_of(name: str, year: int = 1) -> int:
    """그 대회가 열리는 커리어 주차."""
    show = next(s for s in CALENDAR.shows if s.name == name)
    return show.week_of_year + (year - 1) * 52


def won(kind: MatchKind, week: int, show_name: str | None = None) -> WeekReport:
    return WeekReport(
        week=week,
        kind=WeekKind.PLE,
        result=OutcomeKind.WIN,
        match_kind=kind,
        show=(
            next(s for s in CALENDAR.shows if s.name == show_name)
            if show_name
            else None
        ),
    )


class TestTheWrestleManiaShot:
    def test_winning_the_rumble_books_wrestlemania(self) -> None:
        run = make_run(brand=Brand.RAW, week=week_of("로열럼블") - 1)
        after = apply_week(run, won(MatchKind.BATTLE_ROYAL, run.week + 1, "로열럼블"))
        assert after.title_shot

    def test_the_chamber_books_it_too(self) -> None:
        run = make_run(brand=Brand.RAW, week=week_of("엘리미네이션 챔버") - 1)
        after = apply_week(
            run, won(MatchKind.CHAMBER, run.week + 1, "엘리미네이션 챔버")
        )
        assert after.title_shot

    def test_losing_it_books_nothing(self) -> None:
        run = make_run(brand=Brand.RAW, week=week_of("로열럼블") - 1)
        report = won(MatchKind.BATTLE_ROYAL, run.week + 1, "로열럼블")
        after = apply_week(
            run, WeekReport(**{**vars(report), "result": OutcomeKind.LOSS})
        )
        assert not after.title_shot

    def test_the_shot_skips_the_popularity_gate(self) -> None:
        """**도전권의 값어치가 여기 전부 있다** — 자격이 없어도 자리에 선다."""
        week = week_of(WRESTLEMANIA)
        low = WrestlerStats(popularity=20)
        run = make_run(brand=Brand.RAW, week=week - 1, stats=low).evolve(
            title_shot=True
        )
        report = simulate_week(run)
        assert report.title_shot_from is TitleShotSource.EARNED
        assert TITLES[report.title_at_stake].tier is TitleTier.WORLD

    def test_without_the_shot_low_popularity_gets_nothing(self) -> None:
        run = make_run(
            brand=Brand.RAW,
            week=week_of(WRESTLEMANIA) - 1,
            stats=WrestlerStats(popularity=20),
        )
        assert simulate_week(run).title_shot_from is None

    def test_it_is_gone_after_that_wrestlemania(self) -> None:
        week = week_of(WRESTLEMANIA)
        run = make_run(brand=Brand.RAW, week=week - 1).evolve(title_shot=True)
        after = apply_week(run, simulate_week(run))
        assert not after.title_shot

    def test_missing_wrestlemania_burns_it_too(self) -> None:
        """**그 주에 다쳐 결장해도 사라진다.** 리포트가 아니라 달력이 지운다.

        `report.show`로 지우면 결장 주차에는 비어 있어 도전권이 이듬해로 넘어가고,
        30년이면 도전권이 쌓인다.
        """
        week = week_of(WRESTLEMANIA)
        run = make_run(brand=Brand.RAW, week=week - 1).evolve(title_shot=True)
        after = apply_week(run, WeekReport(week=week, kind=WeekKind.OFF))
        assert not after.title_shot


class TestTheBriefcase:
    def test_winning_the_ladder_at_mitb_gives_it(self) -> None:
        run = make_run(brand=Brand.RAW, week=week_of(MITB) - 1)
        after = apply_week(run, won(MatchKind.LADDER, run.week + 1, MITB))
        assert after.briefcase
        assert after.briefcase_week == run.week + 1

    def test_a_ladder_match_on_another_night_gives_nothing(self) -> None:
        """래더는 다른 밤에도 걸린다 (§3-D32). **가방은 그 대회의 것이다.**"""
        run = make_run(brand=Brand.RAW, week=week_of("백래시") - 1)
        after = apply_week(run, won(MatchKind.LADDER, run.week + 1, "백래시"))
        assert not after.briefcase

    def test_cashing_in_books_a_world_title_match(self) -> None:
        run = make_run(brand=Brand.RAW, week=400, stats=WrestlerStats(popularity=20))
        held = run.evolve(briefcase_week=390, flags=frozenset({CASH_IN_PENDING}))
        report = simulate_week(held)
        assert report.title_shot_from is TitleShotSource.BRIEFCASE
        assert TITLES[report.title_at_stake].tier is TitleTier.WORLD
        # 현금화는 지친 챔피언과 둘이 붙는 3분짜리다 — 럼블이 예정된 밤이라도.
        assert report.match_kind is MatchKind.SINGLES

    def test_it_is_single_use(self) -> None:
        run = make_run(brand=Brand.RAW, week=400).evolve(
            briefcase_week=390, flags=frozenset({CASH_IN_PENDING})
        )
        after = apply_week(run, simulate_week(run))
        assert not after.briefcase
        assert CASH_IN_PENDING not in after.flags

    def test_deciding_to_cash_in_survives_a_week_off(self) -> None:
        """신호는 **쓰일 때까지** 남는다. 결장 주차에 지우면 결정이 증발한다."""
        run = make_run(brand=Brand.RAW, week=400).evolve(
            briefcase_week=390, flags=frozenset({CASH_IN_PENDING})
        )
        after = apply_week(run, WeekReport(week=401, kind=WeekKind.OFF))
        assert after.briefcase
        assert CASH_IN_PENDING in after.flags

    def test_a_year_later_the_rule_uses_it(self) -> None:
        """**1년 안에 써야 한다** (2026-08-11 사용자 확인). 안 고르면 규칙이 쓴다 —
        묻는 카드가 안 떠서 못 쓰고 은퇴하는 일이 실측 20판 중 17판이었다.
        """
        # **경기가 있는 주차라야 쓴다.** 기한이 지나도 프로모·결장 주차에는 못 쓴다.
        week = week_of("백래시", year=9)
        run = make_run(
            brand=Brand.RAW, week=week - 1, stats=WrestlerStats(popularity=20)
        )
        expiring = run.evolve(briefcase_week=week - rules.BRIEFCASE_WEEKS)
        assert simulate_week(expiring).title_shot_from is TitleShotSource.BRIEFCASE

    def test_before_the_deadline_it_waits_for_you(self) -> None:
        week = week_of("백래시", year=9)
        run = make_run(
            brand=Brand.RAW, week=week - 1, stats=WrestlerStats(popularity=20)
        )
        fresh = run.evolve(briefcase_week=week - 4)
        assert simulate_week(fresh).title_shot_from is None

    @pytest.mark.parametrize("belt", [Title.WORLD_HEAVYWEIGHT_CHAMPIONSHIP])
    def test_you_cannot_cash_in_on_yourself(self, belt: Title) -> None:
        run = make_run(brand=Brand.RAW, week=week_of("백래시", year=9) - 1).evolve(
            briefcase_week=390,
            flags=frozenset({CASH_IN_PENDING}),
            titles_held=frozenset({belt}),
            titles_won=(belt,),
        )
        assert simulate_week(run).title_shot_from is None
        # 쓰지 못했으니 가방은 그대로다.
        assert apply_week(run, simulate_week(run)).briefcase
