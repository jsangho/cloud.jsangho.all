"""DB 경기 ↔ 위키 결과 줄 짝짓기 테스트 — **본문은 실제 위키에서 떠 왔다.**

픽스처는 `test_ple_card_parser`와 같은 것을 쓴다:

    wiki_royal_rumble_2026_results.txt  Royal Rumble (2026) · rev 1376819544
    wiki_wrestlemania_42_results.txt    WrestleMania 42 · rev 1376818511 · 2일제

**로얄럼블이 핵심 회귀 자리다.** Gunther가 4경기에서 이기고 6경기에서 마지막에
탈락당한다 — 승자 이름으로 짝지으면 여기서 어긋난다.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kayfabe.domain.services.ple_card_parser import parse_results_tables
from kayfabe.domain.services.wiki_result_pairing import MatchCandidate, pair_results

_FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def royal_rumble() -> str:
    return (_FIXTURES / "wiki_royal_rumble_2026_results.txt").read_text(
        encoding="utf-8"
    )


@pytest.fixture(scope="module")
def wrestlemania() -> str:
    return (_FIXTURES / "wiki_wrestlemania_42_results.txt").read_text(encoding="utf-8")


def _candidate(key: str, title: str, *participants: str) -> MatchCandidate:
    return MatchCandidate(key=key, title=title, participants=participants)


class TestPairing:
    def test_a_rumble_pairs_even_though_the_wiki_names_only_two(
        self, royal_rumble: str
    ) -> None:
        """본문은 `Roman Reigns won by last eliminating Gunther` 뿐이다.

        DB는 참가자 다섯을 들고 있다 — 겹치는 이름이 하나뿐이어도 짝지어야 한다.
        """
        cand = _candidate(
            "rr26-men-rumble",
            "Men's Royal Rumble Match",
            "Roman Reigns",
            "CM Punk",
            "John Cena",
            "Logan Paul",
            "Jey Uso",
        )
        paired, unpaired = pair_results([cand], parse_results_tables(royal_rumble))
        assert unpaired == ()
        assert len(paired) == 1
        assert paired[0].winner.names == ("Roman Reigns",)

    def test_a_wrestler_who_wins_once_and_loses_once_does_not_cross_pair(
        self, royal_rumble: str
    ) -> None:
        """🔴 핵심 회귀. Gunther는 4경기 승자이고 6경기에서 마지막에 탈락한다."""
        cands = [
            _candidate(
                "rr26-gunther-styles", "Career Threat Match", "Gunther", "AJ Styles"
            ),
            _candidate(
                "rr26-men-rumble", "Men's Royal Rumble Match", "Roman Reigns", "Gunther"
            ),
        ]
        paired, unpaired = pair_results(cands, parse_results_tables(royal_rumble))
        assert unpaired == ()
        won = {p.candidate.key: p.winner.names for p in paired}
        assert won["rr26-gunther-styles"] == ("Gunther",)
        assert won["rr26-men-rumble"] == ("Roman Reigns",)

    def test_a_team_written_as_name_and_members_still_pairs(
        self, wrestlemania: str
    ) -> None:
        """DB가 `팀명 — 멤버` 로 적어도 멤버까지 꺼내 맞춘다."""
        cand = _candidate(
            "wm42-n1-six",
            "Six-man tag team match",
            "The Usos — Jey Uso, Jimmy Uso",
            "LA Knight",
            "The Vision — Logan Paul, Austin Theory",
        )
        paired, _ = pair_results([cand], parse_results_tables(wrestlemania))
        assert len(paired) == 1
        assert set(paired[0].winner.names) >= {"The Usos", "LA Knight"}

    def test_two_nights_do_not_bleed_into_each_other(self, wrestlemania: str) -> None:
        """번호가 둘 다 1부터다 — 표를 합쳐 세면 여기서 어긋난다."""
        cands = [
            _candidate("n1", "Singles match", "Jacob Fatu", "Drew McIntyre"),
            _candidate("n2", "Singles match", "Finn Bálor", "Dominik Mysterio"),
        ]
        paired, unpaired = pair_results(cands, parse_results_tables(wrestlemania))
        assert unpaired == ()
        won = {p.candidate.key: p.winner.names for p in paired}
        assert won["n1"] == ("Jacob Fatu",)
        assert won["n2"] == ('"The Demon" Finn Bálor',)


class TestRefusingToGuess:
    def test_a_match_with_no_overlap_is_reported_not_dropped(
        self, royal_rumble: str
    ) -> None:
        """못 맞춘 경기가 조용히 사라지면 "결과 없음"과 구분되지 않는다."""
        cand = _candidate("ghost", "Singles match", "Someone Else", "Nobody Here")
        paired, unpaired = pair_results([cand], parse_results_tables(royal_rumble))
        assert paired == ()
        assert [c.key for c in unpaired] == ["ghost"]

    def test_a_tie_is_left_unpaired(self) -> None:
        """두 줄이 같은 점수로 한 경기를 노리면 고르지 않는다."""
        text = (
            "{{Pro wrestling results table\n"
            "|match1 = Alpha defeated Beta by pinfall\n"
            "|match2 = Alpha defeated Beta by submission\n"
            "}}"
        )
        cand = _candidate("tie", "Singles match", "Alpha", "Beta")
        paired, unpaired = pair_results([cand], parse_results_tables(text))
        assert paired == ()
        assert [c.key for c in unpaired] == ["tie"]

    def test_a_no_contest_offers_no_winner_to_pair_with(self) -> None:
        text = (
            "{{Pro wrestling results table\n"
            "|match1 = Alpha and Beta fought to a draw\n"
            "}}"
        )
        cand = _candidate("drawn", "Singles match", "Alpha", "Beta")
        paired, unpaired = pair_results([cand], parse_results_tables(text))
        assert paired == ()
        assert [c.key for c in unpaired] == ["drawn"]

    def test_one_wiki_row_is_never_used_twice(self) -> None:
        text = "{{Pro wrestling results table\n|match1 = Alpha defeated Beta\n}}"
        cands = [
            _candidate("a", "Singles match", "Alpha", "Beta"),
            _candidate("b", "Singles match", "Alpha", "Beta"),
        ]
        paired, unpaired = pair_results(cands, parse_results_tables(text))
        assert len(paired) + len(unpaired) == 2
        assert len(paired) <= 1
