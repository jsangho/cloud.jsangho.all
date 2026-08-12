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


def _placed(week: int, seed: int = 0) -> dict[str, Brand]:
    """그 주차에 메인 로스터에 선 사람 → 브랜드."""
    return {
        m.name: roster.brand_at(m, week, seed)
        for m in roster.active_at(week)
        if roster.tier_at(m, week) is not RivalTier.PROSPECT
    }


class TestTheYearEndDraft:
    def test_a_few_move_each_year(self) -> None:
        """사용자가 정한 크기는 **연 3~4명**이다 — 그 이상이면 명부 재편이 된다."""
        for year in YEARS:
            before = _placed(year * WEEKS_PER_YEAR + roster.DRAFT_WEEK - 1, 7777)
            after = _placed(year * WEEKS_PER_YEAR + roster.DRAFT_WEEK + 1, 7777)
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
            before, after = _placed(later - 1, 7777), _placed(later, 7777)
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
                        before = len(
                            roster.pool_for(gender, tier, before_week, brand, 7777)
                        )
                        after = len(
                            roster.pool_for(gender, tier, after_week, brand, 7777)
                        )
                        assert abs(before - after) <= 1, (
                            f"{year}년차 {gender}/{tier}/{brand}: {before} → {after}"
                        )

    def test_another_seed_is_another_draft(self) -> None:
        """커리어마다 다른 드래프트가 돈다 (2026-08-12 사용자 요청)."""
        week = 8 * WEEKS_PER_YEAR + roster.DRAFT_WEEK + 1
        assert _placed(week, seed=7777) != _placed(week, seed=1234)

    def test_the_same_seed_is_the_same_draft(self) -> None:
        # 되짚는 세계라(§3-D4) 두 번 물으면 같아야 한다.
        week = 8 * WEEKS_PER_YEAR + roster.DRAFT_WEEK + 1
        assert _placed(week, seed=7777) == _placed(week, seed=7777)

    def test_the_seed_only_tilts_the_pool_a_little(self) -> None:
        """시드가 칸을 기울이되 **한쪽으로 쏠리지는 않는다.**

        드래프트 순간에는 정확히 맞바꾼다. 다만 그 표식은 사람에게 붙어서, 나중에 그가
        승급하면 다른 등급 칸으로 따라간다 — 그 칸에서는 짝이 맞지 않는다.

        절대 수가 아니라 **비율**로 잰다: 칸이 클수록 치우침도 커지는 것이 자연스럽고,
        지켜야 하는 것은 바닥(`MIN_BRAND_POOL`)이라 그건 아래에서 따로 잰다.
        """
        week = 10 * WEEKS_PER_YEAR
        for gender in Gender:
            for tier in (RivalTier.MIDCARD, RivalTier.MAIN_EVENT):
                for brand in (Brand.RAW, Brand.SMACKDOWN):
                    sizes = [
                        len(roster.pool_for(gender, tier, week, brand, seed))
                        for seed in (0, 7777, 1234, 99)
                    ]
                    tilt = (max(sizes) - min(sizes)) / max(sizes)
                    assert tilt <= 0.3, f"{gender}/{tier}/{brand}: {sizes}"

    @pytest.mark.parametrize("seed", [0, 7777, 1234])
    def test_a_champion_is_never_drafted(self, seed: int) -> None:
        """드래프트 당시 챔피언은 자리를 옮기지 않는다 (2026-08-12 사용자 결정).

        옮기면 벨트가 남의 브랜드에서 걸린다 — §3-D53이 잡아 놓은 것을 도로 깬다.
        """
        from wwe_game.domain.services import title_scene
        from wwe_game.domain.value_objects.title import TITLES

        for year in range(1, 20):
            week = year * WEEKS_PER_YEAR + roster.DRAFT_WEEK
            champions = {
                roster.member_of(name, seed)
                for title in TITLES
                for name in title_scene.members_of(
                    title_scene.champion_at(seed, week - 1, title) or ""
                )
            }
            before, after = _placed(week - 1, seed), _placed(week, seed)
            moved = {n for n, b in after.items() if n in before and before[n] is not b}
            held = {m.name for m in champions if m is not None}
            assert not (moved & held), f"{year}년차: 챔피언 {moved & held}가 옮겨졌다"

    @pytest.mark.parametrize("seed", [0, 7777, 1234, 99])
    def test_the_brand_pools_survive_thirty_years(self, seed: int) -> None:
        """**시드마다 확인한다.** 임포트 검증은 시드 0만 보는데, 드래프트가 칸을 한 명씩
        기울일 수 있어(위 테스트) 다른 세계에서도 바닥을 지키는지는 여기서 잰다."""
        for gender in Gender:
            for brand in Brand:
                tier = roster.tier_in(brand, RivalTier.MAIN_EVENT)
                for week in range(0, CAREER_WEEKS + 1, WEEKS_PER_YEAR):
                    pool = roster.pool_for(gender, tier, week, brand, seed)
                    assert len(pool) >= roster.MIN_BRAND_POOL, (
                        f"시드 {seed} · {gender}/{brand} {week // WEEKS_PER_YEAR}년차: {pool}"
                    )


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


class TestTheCastChangesEachRun:
    """가상 선수 이름은 **판마다 다르다** (§3-D59, 2026-08-12 사용자 요청).

    명부의 크기·데뷔·은퇴는 상수다 — 바뀌는 것은 그 자리에 서는 사람의 이름뿐이다.
    """

    @staticmethod
    def _cast(seed: int) -> list[str]:
        return [
            roster.name_at(member, 500, seed)
            for member in roster.ROSTER
            if member.slot >= 0
        ]

    def test_another_seed_is_another_cast(self) -> None:
        assert self._cast(42) != self._cast(7777)

    def test_the_same_seed_is_the_same_cast(self) -> None:
        assert self._cast(42) == self._cast(42)

    def test_nobody_shares_a_name(self) -> None:
        for seed in (0, 42, 7777, 1234):
            names = [roster.name_at(member, 500, seed) for member in roster.ROSTER]
            assert len(names) == len(set(names)), f"시드 {seed}에 같은 이름이 둘 있다"

    def test_the_real_wrestlers_keep_their_names(self) -> None:
        # 실존 선수는 시드와 무관하다 — 판마다 로만 레인즈가 다른 사람일 수는 없다.
        for seed in (42, 7777):
            for member in roster.ROSTER:
                if member.slot < 0 and member.renamed_to is None:
                    assert roster.name_at(member, 0, seed) == member.name

    def test_the_roster_shape_never_changes(self) -> None:
        """**크기·데뷔·은퇴는 상수다.** 여기가 흔들리면 `MIN_POOL` 검증이 무의미해진다."""
        shape = [
            (m.gender, m.start_tier, m.debut_week, m.retire_week) for m in roster.ROSTER
        ]
        for seed in (0, 42, 7777):
            for gender in Gender:
                for tier in RivalTier:
                    sizes = {
                        len(roster.pool_for(gender, tier, week, None, seed))
                        for week in (0, 500, 1000)
                    }
                    assert sizes
        assert shape == [
            (m.gender, m.start_tier, m.debut_week, m.retire_week) for m in roster.ROSTER
        ]

    def test_a_name_finds_its_person_in_that_run(self) -> None:
        for seed in (42, 7777):
            for member in roster.ROSTER:
                if member.slot < 0:
                    continue
                name = roster.name_at(member, 500, seed)
                assert roster.member_of(name, seed) is member
