"""연말 드래프트와 활동명 변경 (하네스 §3-D54).

둘 다 **명부의 시간 축에 얹힌 층**이다(§3-D13-1). 브랜드는 연말마다 몇 자리 바뀌고,
이름은 커리어 도중 한 번 바뀐다 — 어느 쪽도 사람을 늘리거나 없애지 않아야 한다.
"""

from __future__ import annotations

import pytest
from wwe_game.domain.constants import roster
from wwe_game.domain.constants.career_clock import CAREER_WEEKS, WEEKS_PER_YEAR
from wwe_game.domain.constants.roster import RivalTier
from wwe_game.domain.value_objects.title import Brand
from wwe_game.domain.value_objects.wrestler_identity import Gender

YEARS = range(1, 30)


def _placed(week: int) -> dict[str, Brand]:
    """그 주차에 메인 로스터에 선 사람 → 브랜드."""
    return {
        m.name: roster.brand_at(m, week)
        for m in roster.active_at(week)
        if roster.tier_at(m, week) is not RivalTier.PROSPECT
    }


class TestTheYearEndDraft:
    def test_a_few_move_each_year(self) -> None:
        """사용자가 정한 크기는 **연 3~4명**이다 — 그 이상이면 명부 재편이 된다."""
        for year in YEARS:
            before = _placed(year * WEEKS_PER_YEAR + roster.DRAFT_WEEK - 1)
            after = _placed(year * WEEKS_PER_YEAR + roster.DRAFT_WEEK + 1)
            moved = [n for n, b in after.items() if n in before and before[n] is not b]
            assert 2 <= len(moved) <= 4, f"{year}년차에 {len(moved)}명이 옮겼다"

    def test_nothing_moves_between_drafts(self) -> None:
        """브랜드가 바뀌는 자리는 **연말 하나뿐**이다.

        콜업(유망주 → 메인)은 등급이 하는 일이라 여기서 보지 않는다 — 두 주차에 모두
        메인 로스터에 있던 사람만 견준다.
        """
        start = 5 * WEEKS_PER_YEAR
        for step in range(1, 3 * WEEKS_PER_YEAR):
            later = start + step
            if (later - roster.DRAFT_WEEK) % WEEKS_PER_YEAR == 0:
                continue  # 드래프트가 서는 주차
            before, after = _placed(later - 1), _placed(later)
            moved = [n for n, b in after.items() if n in before and before[n] is not b]
            assert moved == [], f"{later}주차에 {moved}가 브랜드를 옮겼다"

    def test_the_swap_keeps_both_brands_the_same_size(self) -> None:
        """맞바꾸므로 어느 칸의 인원수도 드래프트로 변하지 않는다."""
        for year in YEARS:
            before_week = year * WEEKS_PER_YEAR + roster.DRAFT_WEEK - 1
            after_week = before_week + 2
            for gender in Gender:
                for tier in (RivalTier.MIDCARD, RivalTier.MAIN_EVENT):
                    for brand in (Brand.RAW, Brand.SMACKDOWN):
                        before = len(roster.pool_for(gender, tier, before_week, brand))
                        after = len(roster.pool_for(gender, tier, after_week, brand))
                        assert abs(before - after) <= 1, (
                            f"{year}년차 {gender}/{tier}/{brand}: {before} → {after}"
                        )

    def test_the_brand_pools_survive_thirty_years(self) -> None:
        for gender in Gender:
            for brand in Brand:
                tier = roster.tier_in(brand, RivalTier.MAIN_EVENT)
                for week in range(0, CAREER_WEEKS + 1, WEEKS_PER_YEAR):
                    pool = roster.pool_for(gender, tier, week, brand)
                    assert len(pool) >= roster.MIN_BRAND_POOL


class TestTheRingNameChanges:
    @pytest.fixture
    def renamers(self) -> tuple[roster.RosterMember, ...]:
        return tuple(m for m in roster.ROSTER if m.renamed_to is not None)

    def test_the_americanos_and_nattie_change(
        self, renamers: tuple[roster.RosterMember, ...]
    ) -> None:
        pairs = {(m.name, m.renamed_to) for m in renamers}
        assert ("브라보 아메리카노", "타일러 베이트") in pairs
        assert ("엘 그란데 아메리카노", "루드비히 카이저") in pairs
        assert ("라요 아메리카노", "피트 던") in pairs
        # 내티로 활동하다 나탈리아가 된다 (2026-08-12 사용자 결정).
        assert ("내티", "나탈리아") in pairs

    def test_the_name_flips_at_its_week(
        self, renamers: tuple[roster.RosterMember, ...]
    ) -> None:
        for member in renamers:
            assert roster.name_at(member, member.rename_week - 1) == member.name
            assert roster.name_at(member, member.rename_week) == member.renamed_to

    def test_they_do_not_all_change_at_once(
        self, renamers: tuple[roster.RosterMember, ...]
    ) -> None:
        # 같은 주에 넷이 개명하면 그 주 인박스가 개명으로만 찬다.
        assert len({m.rename_week for m in renamers}) > 1

    def test_the_pool_calls_them_by_the_name_of_that_week(
        self, renamers: tuple[roster.RosterMember, ...]
    ) -> None:
        for member in renamers:
            after = member.rename_week + 1
            if not member.is_active_at(after):
                continue
            pool = roster.pool_for(member.gender, roster.tier_at(member, after), after)
            assert member.renamed_to in pool
            assert member.name not in pool

    def test_the_old_name_still_finds_the_person(
        self, renamers: tuple[roster.RosterMember, ...]
    ) -> None:
        """로그와 대립에 남은 옛 이름이 없는 사람이 되면 개명이 곧 실종이 된다."""
        for member in renamers:
            assert roster.member_of(member.name) is member
            assert roster.member_of(member.renamed_to or "") is member

    def test_no_name_is_shared_by_two_people(self) -> None:
        names = [m.name for m in roster.ROSTER]
        names += [m.renamed_to for m in roster.ROSTER if m.renamed_to]
        assert len(names) == len(set(names))

    def test_no_name_carries_the_separator(self) -> None:
        # `|`가 그대로 남아 있으면 화면에 "A | B"가 한 사람처럼 찍힌다.
        for member in roster.ROSTER:
            assert "|" not in member.name
            assert "|" not in (member.renamed_to or "")
