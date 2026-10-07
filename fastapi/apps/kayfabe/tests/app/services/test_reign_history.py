"""보드 재위 → 획득 이력 — 중복과 형식을 잠근다.

여기서 지키는 것은 셋이다.

| | |
|---|---|
| 같은 재위를 두 번 넣지 않는다 | 카탈로그와 보드가 같은 사실을 **다른 문자열**로 적는다 |
| 벨트는 계보로 접는다 | 옛 이름의 행이 있으면 현 이름으로 또 넣으면 안 된다 |
| 날짜를 못 읽으면 넣지 않는다 | 중복을 막을 키가 없어 돌릴 때마다 쌓인다 |
"""

from __future__ import annotations

from kayfabe.app.services.reign_history import (
    BoardReign,
    ExistingReign,
    format_won_at,
    missing_board_reigns,
    won_at_to_date,
)


class TestWonAtToDate:
    def test_free_text_catalog_format(self) -> None:
        assert won_at_to_date("Payback — June 16, 2013") == "2013-06-16"

    def test_iso_board_format(self) -> None:
        assert won_at_to_date("2026-09-11") == "2026-09-11"

    def test_single_digit_day(self) -> None:
        assert won_at_to_date("Night of Champions — June 7, 2026") == "2026-06-07"

    def test_unreadable_is_none(self) -> None:
        assert won_at_to_date("언젠가") is None

    def test_every_catalog_row_is_readable(self) -> None:
        """**카탈로그 전체가 환산돼야 중복 판정이 선다.** 하나라도 못 읽으면 그 재위는
        보드 쪽에서 다시 들어온다."""
        from kayfabe.app.services.real_title_catalog import REAL_TITLE_ACQUISITIONS

        unreadable = [
            won_at
            for reigns in REAL_TITLE_ACQUISITIONS.values()
            for _, won_at in reigns
            if won_at_to_date(won_at) is None
        ]
        assert not unreadable, f"날짜를 못 읽는 획득 표기: {unreadable[:5]}"


class TestFormatWonAt:
    def test_matches_the_catalog_spelling(self) -> None:
        assert (
            format_won_at("SmackDown", "2026-09-11") == "SmackDown — September 11, 2026"
        )

    def test_round_trips_back_to_the_same_date(self) -> None:
        assert won_at_to_date(format_won_at("Raw", "2026-07-06")) == "2026-07-06"

    def test_no_event_leaves_just_the_date(self) -> None:
        """대회명이 없는 벨트가 있다(ID 둘). **빈 구분선을 남기지 않는다.**"""
        assert format_won_at(None, "2026-06-26") == "June 26, 2026"


class TestMissingBoardReigns:
    def _reign(self, name: str, belt: str, date: str) -> BoardReign:
        return BoardReign(
            competitor_name=name,
            belt_name=belt,
            won_at=format_won_at("SmackDown", date),
            won_at_date=date,
        )

    def test_new_reign_comes_through(self) -> None:
        missing = missing_board_reigns(
            board=[
                self._reign("Sami Zayn", "Undisputed WWE Championship", "2026-09-11")
            ],
            existing=[
                ExistingReign(
                    "Sami Zayn",
                    "Undisputed WWE Championship",
                    "Night of Champions — June 27, 2026",
                )
            ],
        )
        assert [r.competitor_name for r in missing] == ["Sami Zayn"]

    def test_same_reign_in_a_different_spelling_is_not_duplicated(self) -> None:
        """카탈로그는 자유 텍스트, 보드는 ISO다. **날짜로 맞춘다.**"""
        missing = missing_board_reigns(
            board=[
                self._reign(
                    "Roman Reigns", "World Heavyweight Championship", "2026-04-19"
                )
            ],
            existing=[
                ExistingReign(
                    "Roman Reigns",
                    "World Heavyweight Championship",
                    "WrestleMania 42 Night 2 — April 19, 2026",
                )
            ],
        )
        assert missing == []

    def test_former_belt_name_counts_as_the_same_belt(self) -> None:
        """이력에 `Intercontinental`로 적힌 재위를 `WWE Intercontinental`로 또 넣지 않는다."""
        missing = missing_board_reigns(
            board=[
                self._reign(
                    "The Miz", "WWE Intercontinental Championship", "2016-04-11"
                )
            ],
            existing=[
                ExistingReign(
                    "The Miz", "Intercontinental Championship", "Raw — April 11, 2016"
                )
            ],
        )
        assert missing == []

    def test_a_tag_team_adds_both_people_once(self) -> None:
        board = [
            self._reign("Brad Baylor", "NXT Tag Team Championship", "2026-08-30"),
            self._reign("Ricky Smokes", "NXT Tag Team Championship", "2026-08-30"),
        ]
        missing = missing_board_reigns(board=board, existing=[])
        assert {r.competitor_name for r in missing} == {"Brad Baylor", "Ricky Smokes"}

    def test_the_same_board_reign_twice_in_one_run_is_added_once(self) -> None:
        reign = self._reign(
            "Zaria", "NXT Women's North American Championship", "2026-06-09"
        )
        assert len(missing_board_reigns(board=[reign, reign], existing=[])) == 1
