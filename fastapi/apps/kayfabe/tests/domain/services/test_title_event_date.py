"""`won_at` 문자열 가르기 (`domain/services/title_event_date`).

이 파일이 붙드는 것은 넷이다.

1. 운영에 **실제로 있는 꼴**을 읽는다 (2026-10-20 실측 386/388).
2. 대회 이름 안의 숫자를 날짜로 오인하지 않는다 (`WrestleMania 25`).
3. 못 읽으면 **`None`** 이다 — 지어내면 연대표가 거짓 순서를 말한다.
4. 날짜가 없는 대회명도 이름은 살린다.

순수 함수라 DB가 필요 없다.
"""

from __future__ import annotations

from datetime import date

import pytest

from kayfabe.domain.services.title_event_date import parse_won_at


class TestRealShapes:
    """운영 DB 에서 그대로 가져온 값들."""

    @pytest.mark.parametrize(
        ("raw", "label", "on"),
        [
            ("WrestleMania 25 — April 5, 2009", "WrestleMania 25", date(2009, 4, 5)),
            ("No Mercy — October 8, 2007", "No Mercy", date(2007, 10, 8)),
            ("TLC — December 15, 2013", "TLC", date(2013, 12, 15)),
            (
                "Money in the Bank — July 17, 2011",
                "Money in the Bank",
                date(2011, 7, 17),
            ),
            ("SummerSlam — August 15, 2004", "SummerSlam", date(2004, 8, 15)),
        ],
    )
    def test_event_and_date_split(self, raw: str, label: str, on: date) -> None:
        parsed = parse_won_at(raw)
        assert parsed.event_label == label
        assert parsed.won_on == on

    @pytest.mark.parametrize("raw", ["June 26, 2026", "November 17, 2025"])
    def test_bare_date_has_no_event_label(self, raw: str) -> None:
        """실측 2건 — 대회명 없이 날짜만 있다. 이름을 지어내지 않는다."""
        parsed = parse_won_at(raw)
        assert parsed.event_label is None
        assert parsed.won_on is not None


class TestDoesNotInvent:
    def test_event_number_is_not_a_date(self) -> None:
        """`WrestleMania 25`의 25를 날짜로 읽으면 안 된다."""
        parsed = parse_won_at("WrestleMania 25")
        assert parsed.event_label == "WrestleMania 25"
        assert parsed.won_on is None

    def test_year_inside_the_name_is_not_a_date(self) -> None:
        assert parse_won_at("Crown Jewel (2026)").won_on is None

    def test_impossible_day_is_unknown(self) -> None:
        """`February 30`은 없는 날이다. 1일로 밀어 넣지 않는다."""
        assert parse_won_at("Backlash — February 30, 2020").won_on is None

    def test_unknown_month_is_unknown(self) -> None:
        assert parse_won_at("Backlash — Smarch 3, 2020").won_on is None

    @pytest.mark.parametrize("raw", ["", "   ", None])
    def test_empty_is_all_none(self, raw: str | None) -> None:
        parsed = parse_won_at(raw)
        assert parsed.event_label is None
        assert parsed.won_on is None


class TestTolerance:
    def test_hyphen_works_like_em_dash(self) -> None:
        """위키에서 긁어 온 값이라 구분자 표기가 섞일 수 있다."""
        assert parse_won_at("Backlash - May 9, 2026").won_on == date(2026, 5, 9)

    def test_en_dash_works_too(self) -> None:
        assert parse_won_at("Backlash – May 9, 2026").won_on == date(2026, 5, 9)

    def test_extra_space_after_comma(self) -> None:
        assert parse_won_at("Backlash — May 9,  2026").won_on == date(2026, 5, 9)
