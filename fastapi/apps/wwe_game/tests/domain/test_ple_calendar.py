"""달력이 해마다 다시 뽑힌다 (하네스 §3-D71, 2026-08-13).

이 파일이 잠그는 것은 한 문장이다 — **두 번째 해가 첫 해와 같으면 안 된다.**
2026-08-12까지 달력은 상수였고, 30년 내내 6월은 클래시였다. 사용자가 다섯 규칙을
정해 그 상수를 풀었고, 여기서 다섯 개를 각각 잠근다.

시드를 여러 개 도는 테스트가 많다. **한 시드로는 확률 규칙이 잡히지 않는다** —
서바이버의 옛 얼굴은 네 해에 한 번이고, 유동 대회의 달은 시드마다 다르다.
"""

from __future__ import annotations

import pytest
from _helpers import make_run  # noqa: I001
from wwe_game.domain.constants import career_rules as rules
from wwe_game.domain.constants.career_clock import WEEKS_PER_YEAR
from wwe_game.domain.constants.ple_calendar import (
    CLASH_SERIES,
    MAIN_CALENDAR,
    MITB,
    NIGHT_OF_CHAMPIONS,
    QUIET_MONTH,
    RUMBLE_TWO_NIGHTS_FROM,
    SURVIVOR_SERIES,
    SURVIVOR_SERIES_CLASSIC,
    WRESTLEMANIA,
    calendar_for,
)
from wwe_game.domain.services.week_simulation import simulate_week, tournament_round_at
from wwe_game.domain.value_objects.match_kind import SIGNATURE_MATCHES, MatchKind
from wwe_game.domain.value_objects.title import Brand
from wwe_game.domain.value_objects.week_report import WeekKind

SEEDS = (1, 42, 777, 12345, 98765)
YEARS = range(1, 31)

FIXED = {"로열럼블", "엘리미네이션 챔버", WRESTLEMANIA, "백래시", "서머슬램"}
"""달이 고정된 대회. 서바이버는 이름이 갈리므로 여기 없다 — 아래에서 따로 본다."""

FLOATING = {CLASH_SERIES, NIGHT_OF_CHAMPIONS, MITB, "크라운 주얼"}


def base_name(name: str) -> str:
    """개최지를 뗀 이름. **접두사로만 자른다** — "머니 인 더 뱅크"에도 " 인 "이 있다."""
    return CLASH_SERIES if name.startswith(f"{CLASH_SERIES} 인 ") else name


def names_in(calendar, year: int) -> set[str]:
    return {base_name(show.name) for show in calendar.shows_in(year)}


def months_of(calendar, year: int) -> dict[str, int]:
    return {
        base_name(show.name): show.month
        for show in calendar.shows_in(year)
        if not show.is_special
    }


# ── ① 달이 해마다 바뀐다 ─────────────────────────────────────


class TestTheMonthsMoveEachYear:
    @pytest.mark.parametrize("seed", SEEDS)
    def test_the_fixed_six_never_move(self, seed: int) -> None:
        """럼블 1월 · 챔버 2월 · 레슬매니아 4월 · 백래시 5월 · 서머슬램 8월 · 서바이버 11월."""
        calendar = calendar_for(Brand.RAW, seed)
        pinned = {
            "로열럼블": 1,
            "엘리미네이션 챔버": 2,
            WRESTLEMANIA: 4,
            "백래시": 5,
            "서머슬램": 8,
        }
        for year in YEARS:
            months = months_of(calendar, year)
            for name, month in pinned.items():
                assert months[name] == month, f"{year}년차 {name}"
            survivor = months.get(SURVIVOR_SERIES, months.get(SURVIVOR_SERIES_CLASSIC))
            assert survivor == 11, f"{year}년차 서바이버"

    @pytest.mark.parametrize("seed", SEEDS)
    def test_the_floating_four_land_in_the_leftover_months(self, seed: int) -> None:
        calendar = calendar_for(Brand.RAW, seed)
        for year in YEARS:
            months = months_of(calendar, year)
            drawn = {months[name] for name in FLOATING}
            assert drawn <= set(MAIN_CALENDAR.float_months)
            assert len(drawn) == len(FLOATING), "두 대회가 같은 달에 섰다"

    @pytest.mark.parametrize("seed", SEEDS)
    def test_one_candidate_month_is_always_empty(self, seed: int) -> None:
        """**후보가 대회보다 하나 많다** — 그 빈 달이 해마다 옮겨 다닌다."""
        calendar = calendar_for(Brand.RAW, seed)
        empty = {
            (
                set(MAIN_CALENDAR.float_months)
                - set(months_of(calendar, year).values())
            ).pop()
            for year in YEARS
        }
        assert len(empty) > 1, "빈 달이 30년 내내 같은 달이다"

    @pytest.mark.parametrize("seed", SEEDS)
    def test_every_show_still_happens_every_year(self, seed: int) -> None:
        """달이 움직여도 **대회가 사라지지는 않는다.**"""
        calendar = calendar_for(Brand.RAW, seed)
        for year in YEARS:
            names = names_in(calendar, year)
            assert FIXED | FLOATING <= names
            assert SURVIVOR_SERIES in names or SURVIVOR_SERIES_CLASSIC in names

    def test_two_seeds_write_two_calendars(self) -> None:
        first = months_of(calendar_for(Brand.RAW, 1), 1)
        second = months_of(calendar_for(Brand.RAW, 2), 1)
        assert first != second

    @pytest.mark.parametrize("seed", SEEDS)
    def test_the_same_seed_writes_the_same_calendar(self, seed: int) -> None:
        """세이브를 다시 열면 같은 달력이어야 한다 (§3-D4)."""
        again = calendar_for(Brand.RAW, seed)
        for year in (1, 7, 30):
            assert months_of(calendar_for(Brand.RAW, seed), year) == months_of(
                again, year
            )

    @pytest.mark.parametrize("seed", SEEDS)
    def test_december_stays_empty(self, seed: int) -> None:
        """**12월은 쉰다** (§3-D21-1). 달이 유동이 돼도 그 결정은 그대로다."""
        calendar = calendar_for(Brand.RAW, seed)
        for year in YEARS:
            ple = [s for s in calendar.shows_in(year) if not s.is_special]
            assert all(s.month != QUIET_MONTH for s in ple)

    @pytest.mark.parametrize("seed", SEEDS)
    def test_nxt_keeps_its_fixed_calendar(self, seed: int) -> None:
        """육성 브랜드는 유동 대회가 없다 — 큰 무대가 귀한 것이 그 브랜드의 성격이다."""
        calendar = calendar_for(Brand.NXT, seed)
        first = months_of(calendar, 1)
        assert all(months_of(calendar, year) == first for year in YEARS)


# ── ② 특별 방송은 가장 먼 자리에 선다 ────────────────────────


class TestTheSpecialsFillTheWidestGaps:
    @pytest.mark.parametrize("seed", SEEDS)
    def test_four_a_year(self, seed: int) -> None:
        calendar = calendar_for(Brand.RAW, seed)
        for year in YEARS:
            specials = [s for s in calendar.shows_in(year) if s.is_special]
            assert len(specials) == MAIN_CALENDAR.special_count

    @pytest.mark.parametrize("seed", SEEDS)
    def test_the_year_end_hole_always_gets_one(self, seed: int) -> None:
        """11월과 이듬해 1월 사이는 8주가 빈다 — 그 해 가장 넓은 자리 중 하나다."""
        calendar = calendar_for(Brand.RAW, seed)
        for year in YEARS:
            weeks = {s.week_of_year for s in calendar.shows_in(year) if s.is_special}
            assert any(week > 46 for week in weeks), f"{year}년차 연말이 비었다"

    @pytest.mark.parametrize("seed", SEEDS)
    def test_a_special_never_stands_on_a_qualifier_week(self, seed: int) -> None:
        """**예선 주차에 특별 방송이 서면 대진이 끊긴다** (§3-D33).

        그 주가 특별 방송의 것이 되어 올라간 사람이 없는 채로 결승이 온다.
        """
        calendar = calendar_for(Brand.RAW, seed)
        for year in YEARS:
            final = calendar.week_of(
                NIGHT_OF_CHAMPIONS, (year - 1) * WEEKS_PER_YEAR + 1
            )
            assert final is not None
            blocked = {final - back for back in range(1, rules.TOURNAMENT_ROUNDS)}
            specials = {s.week_of_year for s in calendar.shows_in(year) if s.is_special}
            assert not specials & blocked

    @pytest.mark.parametrize("seed", SEEDS)
    def test_a_special_never_shares_a_week_with_a_show(self, seed: int) -> None:
        calendar = calendar_for(Brand.RAW, seed)
        for year in YEARS:
            weeks = [s.week_of_year for s in calendar.shows_in(year)]
            assert len(set(weeks)) == len(weeks)

    @pytest.mark.parametrize("seed", SEEDS)
    def test_the_quarterly_grid_is_gone(self, seed: int) -> None:
        """분기 고정이었을 때는 3·6·9·12월이었다. 이제 간격이 자리를 정한다."""
        calendar = calendar_for(Brand.RAW, seed)
        grids = {
            tuple(s.week_of_year for s in calendar.shows_in(year) if s.is_special)
            for year in YEARS
        }
        assert len(grids) > 1, "특별 방송 자리가 30년 내내 같다"


# ── ③ 로열럼블은 3년차부터 이틀 ──────────────────────────────


class TestTheRumbleGrowsToTwoNights:
    @pytest.mark.parametrize("seed", SEEDS)
    def test_one_night_until_the_third_year(self, seed: int) -> None:
        calendar = calendar_for(Brand.RAW, seed)
        for year in range(1, RUMBLE_TWO_NIGHTS_FROM):
            rumble = next(s for s in calendar.shows_in(year) if s.name == "로열럼블")
            assert rumble.nights == 1, f"{year}년차"

    @pytest.mark.parametrize("seed", SEEDS)
    def test_two_nights_from_the_third_year_on(self, seed: int) -> None:
        calendar = calendar_for(Brand.RAW, seed)
        for year in range(RUMBLE_TWO_NIGHTS_FROM, 31):
            rumble = next(s for s in calendar.shows_in(year) if s.name == "로열럼블")
            assert rumble.nights == 2, f"{year}년차"

    @pytest.mark.parametrize("seed", SEEDS)
    def test_the_big_two_were_always_two_nights(self, seed: int) -> None:
        """레슬매니아·서머슬램은 1년차부터 이틀이다 (§3-D71, 2026-08-12)."""
        calendar = calendar_for(Brand.RAW, seed)
        for year in YEARS:
            shows = {s.name: s for s in calendar.shows_in(year)}
            assert shows[WRESTLEMANIA].nights == 2
            assert shows["서머슬램"].nights == 2


# ── ④ 서바이버 시리즈의 두 얼굴 ──────────────────────────────


class TestSurvivorSeriesHasTwoFaces:
    def test_both_faces_show_up_over_thirty_years(self) -> None:
        """기본은 워게임즈이고 **가끔** 전통 제거 매치다 — 로고가 둘인 이유다."""
        faces: set[str] = set()
        for seed in SEEDS:
            calendar = calendar_for(Brand.RAW, seed)
            for year in YEARS:
                faces |= {
                    s.name
                    for s in calendar.shows_in(year)
                    if s.name.startswith("서바이버")
                }
        assert faces == {SURVIVOR_SERIES, SURVIVOR_SERIES_CLASSIC}

    def test_wargames_is_the_usual_face(self) -> None:
        counts = {SURVIVOR_SERIES: 0, SURVIVOR_SERIES_CLASSIC: 0}
        for seed in SEEDS:
            calendar = calendar_for(Brand.RAW, seed)
            for year in YEARS:
                for show in calendar.shows_in(year):
                    if show.name in counts:
                        counts[show.name] += 1
        assert counts[SURVIVOR_SERIES] > counts[SURVIVOR_SERIES_CLASSIC] * 2

    @pytest.mark.parametrize("seed", SEEDS)
    def test_the_logo_follows_the_face(self, seed: int) -> None:
        """사용자가 가져온 로고 둘이 각자의 해에 걸린다."""
        logos = {
            SURVIVOR_SERIES: "11_survivor_series_war",
            SURVIVOR_SERIES_CLASSIC: "11_survivor_series_elimi",
        }
        calendar = calendar_for(Brand.RAW, seed)
        for year in YEARS:
            for show in calendar.shows_in(year):
                if show.name in logos:
                    assert show.logo == logos[show.name]

    def test_the_ring_format_follows_the_face_too(self) -> None:
        """**이름이 규칙의 손잡이다** — 얼굴이 갈리면 링 위의 형식도 갈린다."""
        assert SIGNATURE_MATCHES[SURVIVOR_SERIES] is MatchKind.WARGAMES
        assert (
            SIGNATURE_MATCHES[SURVIVOR_SERIES_CLASSIC] is MatchKind.SURVIVOR_ELIMINATION
        )

    @pytest.mark.parametrize("seed", SEEDS)
    def test_the_night_actually_books_that_match(self, seed: int) -> None:
        calendar = calendar_for(Brand.RAW, seed)
        for year in (6, 7, 8, 9, 10):
            show = next(
                s for s in calendar.shows_in(year) if s.name.startswith("서바이버")
            )
            week = (year - 1) * WEEKS_PER_YEAR + show.week_of_year
            run = make_run(seed=seed, brand=Brand.RAW, week=week - 1)
            report = simulate_week(run)
            if report.kind is not WeekKind.PLE:
                continue
            assert report.match_kind is SIGNATURE_MATCHES[show.name]


# ── ⑤ 클래시 앞뒤 한 주는 해외 ───────────────────────────────


class TestTheClashKeepsTheTourOverseas:
    @pytest.mark.parametrize("seed", SEEDS)
    def test_the_host_city_finishes_the_name(self, seed: int) -> None:
        """이름의 절반이 그 해의 개최지다 — "클래시 인 ○○"."""
        calendar = calendar_for(Brand.RAW, seed)
        for year in YEARS:
            clash = next(
                s for s in calendar.shows_in(year) if s.name.startswith(CLASH_SERIES)
            )
            assert clash.name.startswith(f"{CLASH_SERIES} 인 ")
            assert clash.region is not None

    @pytest.mark.parametrize("seed", SEEDS)
    def test_the_host_changes_over_the_years(self, seed: int) -> None:
        calendar = calendar_for(Brand.RAW, seed)
        hosts = {
            next(
                s for s in calendar.shows_in(year) if s.name.startswith(CLASH_SERIES)
            ).name
            for year in YEARS
        }
        assert len(hosts) > 1

    @pytest.mark.parametrize("seed", SEEDS)
    def test_the_tour_stays_for_the_weeks_on_either_side(self, seed: int) -> None:
        """대회 하나만 해외로 두면 건너뛰듯 대륙을 옮겼다 돌아오는 그림이 된다."""
        calendar = calendar_for(Brand.RAW, seed)
        for year in (1, 5, 12, 30):
            clash = next(
                s for s in calendar.shows_in(year) if s.name.startswith(CLASH_SERIES)
            )
            base = (year - 1) * WEEKS_PER_YEAR + clash.week_of_year
            for week in (base - 1, base, base + 1):
                assert calendar.tour_region(week) is clash.region

    @pytest.mark.parametrize("seed", SEEDS)
    def test_the_rest_of_the_year_is_not_pinned(self, seed: int) -> None:
        calendar = calendar_for(Brand.RAW, seed)
        clash = next(s for s in calendar.shows_in(1) if s.name.startswith(CLASH_SERIES))
        pinned = {clash.week_of_year - 1, clash.week_of_year, clash.week_of_year + 1}
        for week in range(1, WEEKS_PER_YEAR + 1):
            if week not in pinned:
                assert calendar.tour_region(week) is None

    @pytest.mark.parametrize("seed", SEEDS)
    def test_the_narration_stands_where_the_calendar_says(self, seed: int) -> None:
        """무대 문장과 리포트 머리가 어긋나면 그 밤이 두 곳에서 열린 것이 된다 (§3-D69)."""
        from wwe_game.adapter.outbound.narration.rule_narrator import RuleNarrator
        from wwe_game.adapter.outbound.narration.templates import VENUES

        calendar = calendar_for(Brand.RAW, seed)
        narrator = RuleNarrator()
        for year in (6, 11, 20):
            clash = next(
                s for s in calendar.shows_in(year) if s.name.startswith(CLASH_SERIES)
            )
            assert clash.region is not None
            base = (year - 1) * WEEKS_PER_YEAR + clash.week_of_year
            run = make_run(seed=seed, brand=Brand.RAW, week=base)
            for week in (base - 1, base, base + 1):
                venue = narrator.venue_of(run, week)
                assert venue in VENUES[clash.region] or venue in _stadiums(clash.region)


def _stadiums(region):
    from wwe_game.adapter.outbound.narration.templates import STADIUMS

    return STADIUMS[region]


# ── 달력이 바뀌어도 규칙은 그 해를 따라간다 ──────────────────


class TestTheRulesFollowTheMovingCalendar:
    @pytest.mark.parametrize("seed", SEEDS)
    def test_the_tournament_final_moves_with_the_show(self, seed: int) -> None:
        """§3-D33의 예선 둘 + 결승이 **그 해의** 나이트 오브 챔피언스에 붙는다."""
        calendar = calendar_for(Brand.RAW, seed)
        for year in (4, 9, 17, 30):
            final = calendar.week_of(
                NIGHT_OF_CHAMPIONS, (year - 1) * WEEKS_PER_YEAR + 1
            )
            assert final is not None
            base = (year - 1) * WEEKS_PER_YEAR
            run = make_run(seed=seed, brand=Brand.RAW)
            rounds = [
                tournament_round_at(run, base + final - back)
                for back in reversed(range(rules.TOURNAMENT_ROUNDS))
            ]
            assert rounds == [1, 2, 3]
            assert tournament_round_at(run, base + final - rules.TOURNAMENT_ROUNDS) == 0
