"""대진표 파서 테스트 — **본문은 실제 위키에서 떠 왔다.**

지어낸 본문으로 쓰면 안 되는 이유가 이 저장소에 이미 있다. `champion_table_parser`
첫 판이 실제 본문에 한 번도 안 돌아간 채 세 가지를 동시에 틀렸다(사진 두 장 행을
챔피언으로 집고, 사진 없는 행 넷을 통째로 버렸다). 픽스처 둘은 그래서 실측이다:

    wiki_mitb_2026_matches.txt        Money in the Bank (2026) · rev 1377369432 · 카드형
    wiki_wrestlemania_42_results.txt  WrestleMania 42 · rev 1376818511 · 결과형 · 2일제
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kayfabe.domain.services.ple_card_parser import (
    card_matches,
    parse_results_tables,
)

_FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def mitb() -> str:
    return (_FIXTURES / "wiki_mitb_2026_matches.txt").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def wrestlemania() -> str:
    return (_FIXTURES / "wiki_wrestlemania_42_results.txt").read_text(encoding="utf-8")


class TestCardForm:
    """아직 안 열린 대회 — `vs.`로 적힌 대진."""

    def test_the_whole_announced_card_is_read(self, mitb: str) -> None:
        tables = parse_results_tables(mitb)
        assert len(tables) == 1
        assert tables[0].caption is None
        assert len(tables[0].matches) == 5

    def test_a_ladder_match_keeps_every_entrant(self, mitb: str) -> None:
        men = parse_results_tables(mitb)[0].matches[0]
        assert men.is_card
        assert [c.name for c in men.competitors] == [
            "Bron Breakker",
            "Je'Von Evans",
            "Trick Williams",
            "Penta",
            "CM Punk",
            "1 TBD",
        ]

    def test_an_open_slot_is_marked_not_guessed(self, mitb: str) -> None:
        """`1 TBD`는 이름이 아니다. 비워 두는 것과도 다르다 — 자리는 존재한다."""
        men = parse_results_tables(mitb)[0].matches[0]
        assert men.competitors[-1].undetermined is True
        assert men.competitors[0].undetermined is False

    def test_the_champion_marker_is_lifted_off_the_name(self, mitb: str) -> None:
        whc = parse_results_tables(mitb)[0].matches[2]
        assert [(c.name, c.is_champion) for c in whc.competitors] == [
            ("Roman Reigns", True),
            ("LA Knight", False),
        ]

    def test_an_undecided_opponent_is_not_resolved(self, mitb: str) -> None:
        """`Becky Lynch or Liv Morgan` — 위키도 모르는 것을 화면이 정하면 안 된다."""
        row = parse_results_tables(mitb)[0].matches[4]
        assert len(row.competitors) == 2
        other = row.competitors[1]
        assert other.undetermined is True
        assert other.name == "Becky Lynch or Liv Morgan"

    def test_the_stipulation_rides_along(self, mitb: str) -> None:
        whc = parse_results_tables(mitb)[0].matches[2]
        assert whc.stipulation == "Singles match for the World Heavyweight Championship"


class TestTwoNightEvent:
    """**핵심 회귀.** 문서 전체에 정규식을 한 번 돌리면 2일차가 1일차를 덮어쓴다."""

    def test_each_night_is_its_own_table(self, wrestlemania: str) -> None:
        tables = parse_results_tables(wrestlemania)
        assert len(tables) == 2
        assert tables[0].caption == "Night 1 (April 18)"
        assert tables[1].caption == "Night 2 (April 19)"

    def test_both_nights_number_from_one_and_neither_is_lost(
        self, wrestlemania: str
    ) -> None:
        tables = parse_results_tables(wrestlemania)
        assert [m.number for m in tables[0].matches] == [1, 2, 3, 4, 5, 6, 7]
        assert [m.number for m in tables[1].matches] == [1, 2, 3, 4, 5, 6]

    def test_the_stipulation_stays_with_its_own_night(self, wrestlemania: str) -> None:
        """번호가 겹치므로 문서 단위로 모으면 여기서 어긋난다 — 실제로 어긋났었다."""
        night1, night2 = parse_results_tables(wrestlemania)
        assert night1.matches[0].stipulation == "Six-man tag team match"
        assert night2.matches[0].stipulation == "Singles match"

    def test_spaced_pipes_are_read_too(self, wrestlemania: str) -> None:
        """Night 1은 `|match1 =`, Night 2는 `| match1 =`다. 같은 문서 안에서 섞인다."""
        assert len(parse_results_tables(wrestlemania)[1].matches) == 6


class TestResultFormIsNotACard:
    """끝난 대회의 `defeated` 줄을 대진으로 옮기면 승자가 예정 경기로 둔갑한다."""

    def test_a_finished_match_is_not_a_card(self, wrestlemania: str) -> None:
        row = parse_results_tables(wrestlemania)[0].matches[4]
        assert "defeated" in row.raw
        assert row.is_card is False

    def test_no_competitors_are_offered_for_a_finished_match(
        self, wrestlemania: str
    ) -> None:
        for table in parse_results_tables(wrestlemania):
            for row in table.matches:
                assert row.competitors == ()

    def test_collecting_cards_skips_a_finished_event_entirely(
        self, wrestlemania: str
    ) -> None:
        assert card_matches(parse_results_tables(wrestlemania)) == ()

    def test_collecting_cards_flattens_an_announced_event(self, mitb: str) -> None:
        assert len(card_matches(parse_results_tables(mitb))) == 5


class TestEdges:
    def test_no_table_means_no_tables(self) -> None:
        assert parse_results_tables("==Background==\n아직 발표되지 않았다.") == ()

    def test_a_nested_template_does_not_close_the_table_early(self) -> None:
        """`}}`를 먼저 만나는 자리로 자르면 안쪽 템플릿에서 끊긴다."""
        text = (
            "{{Pro wrestling results table\n"
            "|match1 = A {{small|x}} vs. B\n"
            "|stip1  = Singles match\n"
            "|match2 = C vs. D\n"
            "|stip2  = Tag team match\n"
            "}}"
        )
        tables = parse_results_tables(text)
        assert len(tables) == 1
        assert len(tables[0].matches) == 2

    def test_an_escort_is_not_a_competitor(self) -> None:
        text = (
            "{{Pro wrestling results table\n"
            "|match1 = Bron Breakker (with Paul Heyman) vs. Seth Rollins\n"
            "}}"
        )
        row = parse_results_tables(text)[0].matches[0]
        assert [c.name for c in row.competitors] == ["Bron Breakker", "Seth Rollins"]

    def test_a_one_sided_row_is_not_a_card(self) -> None:
        """`vs.`가 없으면 대진이 아니다. 한 칸짜리 카드를 만들지 않는다."""
        text = "{{Pro wrestling results table\n|match1 = Battle royal\n}}"
        assert parse_results_tables(text)[0].matches[0].is_card is False
