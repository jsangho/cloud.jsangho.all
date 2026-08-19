"""그 사람의 무기고 (하네스 §3-D91).

지키는 것 셋:

1. **데이터가 있으면 그대로 쓴다** — 사용자가 채운 표기를 코드가 다시 짓지 않는다
2. **없으면 굴린다** — `Not Yet`인 선수도, 30년 뒤의 가상 선수도 이름 있는 수를 쓴다
3. **한 사람의 무기고는 늘 같다** — 주차마다 바뀌면 "그 사람의 것"이 아니다
"""

from __future__ import annotations

from wwe_game.domain.constants import roster
from wwe_game.domain.services import arsenal
from wwe_game.domain.value_objects.finisher import MOVES, MoveFamily

KNOWN = "CM 펑크"
"""CSV에 시그니처가 여섯 개 적힌 선수."""

MADE_UP = "디온 스파크"
"""가상 선수 — 데이터가 있을 리 없다."""


class TestTheDataWins:
    def test_a_listed_wrestler_keeps_the_written_moves(self) -> None:
        assert arsenal.signatures_of(KNOWN) == roster.signatures_of(KNOWN)
        assert len(arsenal.signatures_of(KNOWN)) > 1

    def test_the_finisher_comes_from_the_written_ones(self) -> None:
        assert arsenal.finisher_of(KNOWN) in roster.finishers_of(KNOWN)

    def test_the_roster_carries_most_of_the_names(self) -> None:
        """**대부분이 데이터로 채워져 있다** — 굴림은 빈 자리를 메우는 것이지 기본이 아니다."""
        assert len(roster.SIGNATURES) > 150
        assert len(roster.FINISHER_NAMES) > 150


class TestTheRestGetRolled:
    def test_someone_without_data_still_has_moves(self) -> None:
        """서른 해가 지나면 링에 서는 사람 대부분이 가상 선수다 (§3-D59)."""
        rolled = arsenal.signatures_of(MADE_UP)
        assert rolled
        assert len(rolled) <= arsenal.ROLLED_RANGE[1]

    def test_the_same_person_always_has_the_same_arsenal(self) -> None:
        assert arsenal.signatures_of(MADE_UP) == arsenal.signatures_of(MADE_UP)
        assert arsenal.finisher_of(MADE_UP) == arsenal.finisher_of(MADE_UP)

    def test_two_people_do_not_share_one_arsenal(self) -> None:
        assert arsenal.signatures_of("케이든 하트") != arsenal.signatures_of(MADE_UP)

    def test_no_one_repeats_a_move(self) -> None:
        for name in ("케이든 하트", MADE_UP, "놀란 폭스", "하야토 이시카와"):
            rolled = arsenal.signatures_of(name)
            assert len(set(rolled)) == len(rolled)

    def test_a_known_family_keeps_the_moves_in_it(self) -> None:
        """플레이어는 자기 스타일을 안다 — 하늘을 나는 선수가 암바를 시그니처로 쓰지 않는다."""
        rolled = arsenal.signatures_of("장상호", MoveFamily.AERIAL)
        assert set(rolled) <= set(MOVES[MoveFamily.AERIAL])
