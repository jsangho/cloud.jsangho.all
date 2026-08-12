"""명부의 브랜드 축 (하네스 §3-D53).

이 파일이 잠그는 것은 한 문장이다 — **그 밤에 선 사람은 그 브랜드 사람이다.**
NXT 대회 카드에 메인 로스터 이름이 서면 브랜드가 있다는 사실 자체가 화면에서 사라진다.
"""

from __future__ import annotations

import pytest
from _helpers import make_run  # noqa: I001
from wwe_game.domain.constants import roster
from wwe_game.domain.constants.career_clock import CAREER_WEEKS, WEEKS_PER_YEAR
from wwe_game.domain.constants.ple_calendar import calendar_for
from wwe_game.domain.constants.roster import RivalTier
from wwe_game.domain.services import rivalry_engine, show_report, title_scene
from wwe_game.domain.services.seeded_roll import SeededRoll
from wwe_game.domain.value_objects.title import TITLES, Brand, Title, titles_of
from wwe_game.domain.value_objects.wrestler_identity import Gender
from wwe_game.domain.value_objects.wrestler_stats import WrestlerStats

SEED = 7777
WEEKS = (0, 200, 500, 900, 1400)


class TestTheRosterKnowsItsBrand:
    @pytest.mark.parametrize("week", WEEKS)
    def test_a_prospect_is_in_developmental(self, week: int) -> None:
        """명부가 그렇게 분류돼 있다 — 원본에서 NXT·Evolve 70명이 전원 유망주다."""
        for member in roster.active_at(week):
            if roster.tier_at(member, week) is RivalTier.PROSPECT:
                assert roster.brand_at(member, week) is Brand.NXT

    @pytest.mark.parametrize("week", WEEKS)
    def test_the_main_roster_has_no_prospects(self, week: int) -> None:
        for brand in (Brand.RAW, Brand.SMACKDOWN):
            for gender in Gender:
                assert roster.pool_for(gender, RivalTier.PROSPECT, week, brand) == ()

    def test_asking_for_a_missing_tier_is_folded(self) -> None:
        # 접지 않고 물으면 빈 명단이 오고, 그러면 벨트 주인이 사라진다.
        assert roster.tier_in(Brand.NXT, RivalTier.MAIN_EVENT) is RivalTier.PROSPECT
        assert roster.tier_in(Brand.RAW, RivalTier.PROSPECT) is RivalTier.MIDCARD

    def test_every_brand_keeps_a_top_pool_for_thirty_years(self) -> None:
        for gender in Gender:
            for brand in Brand:
                tier = roster.tier_in(brand, RivalTier.MAIN_EVENT)
                for week in range(0, CAREER_WEEKS + 1, WEEKS_PER_YEAR):
                    pool = roster.pool_for(gender, tier, week, brand)
                    assert len(pool) >= roster.MIN_BRAND_POOL, (
                        f"{gender}/{brand} {week // WEEKS_PER_YEAR}년차: {pool}"
                    )


class TestTheBeltStaysHome:
    @pytest.mark.parametrize("title", sorted(TITLES, key=lambda t: t.value))
    @pytest.mark.parametrize("week", WEEKS)
    def test_a_champion_stands_on_that_brand(self, title: Title, week: int) -> None:
        spec = TITLES[title]
        holder = title_scene.champion_at(SEED, week, title)
        assert holder is not None
        member = roster.member_of(holder)
        assert member is not None
        if len(spec.brands) == 1:
            assert roster.brand_at(member, week) is next(iter(spec.brands))
        else:
            # 브랜드 통합 벨트(여성부 태그팀)는 메인 로스터 어느 쪽이어도 된다.
            assert roster.brand_at(member, week) in spec.brands

    @pytest.mark.parametrize("title", sorted(TITLES, key=lambda t: t.value))
    @pytest.mark.parametrize("week", WEEKS)
    def test_a_retired_wrestler_never_holds_a_belt(
        self, title: Title, week: int
    ) -> None:
        """은퇴한 사람이 벨트를 들고 있으면 명부의 시간 축이 무의미해진다 (§3-D13-1)."""
        holder = title_scene.champion_at(SEED, week, title)
        member = roster.member_of(holder or "")
        assert member is not None
        assert member.is_active_at(week)


class TestTheNightIsOneBrand:
    @pytest.mark.parametrize("brand", list(Brand))
    def test_the_card_only_has_that_brand(self, brand: Brand) -> None:
        show = calendar_for(brand).shows[0]
        week = show.week_of_year + 52 * 8
        run = make_run(seed=SEED, week=week + 1, brand=brand)
        report = show_report.build_night(run, week)
        assert report.card, "카드가 비었다 — 브랜드로 거르다 명단이 말랐다"
        for match in report.card:
            for name in (match.left, match.right):
                member = roster.member_of(name)
                assert member is not None
                assert roster.brand_at(member, week) is brand

    @pytest.mark.parametrize("brand", list(Brand))
    def test_my_rival_is_on_my_brand(self, brand: Brand) -> None:
        run = make_run(
            seed=SEED,
            week=300,
            brand=brand,
            stats=WrestlerStats(popularity=70, in_ring=70),
        )
        rival = rivalry_engine.pick_rival(run, SeededRoll(SEED, 300, "test"))
        assert rival is not None
        member = roster.member_of(rival)
        assert member is not None
        assert roster.brand_at(member, 300) is brand

    def test_the_titles_of_a_brand_are_that_brands(self) -> None:
        # 카드가 거는 벨트는 `titles_of(brand, gender)`가 정한다 — 여기가 어긋나면
        # 브랜드를 걸러도 남의 벨트가 그 밤에 걸린다.
        for brand in Brand:
            for gender in Gender:
                for title in titles_of(brand, gender):
                    assert brand in TITLES[title].brands
