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
    """**위상과 브랜드는 다른 축이다** (§3-D95, 2026-08-19 개정).

    예전에는 유망주면 NXT였다 — 그러면 육성 브랜드 안에 위상이 없어서 NXT 챔피언이 그
    주의 신인과 같은 확률로 뽑혔다. 사용자가 *"비정상적인 챔피언들이 속출한다"*고 짚은
    자리이고, 그래서 브랜드는 `develops`가 따로 든다.
    """

    @pytest.mark.parametrize("week", WEEKS)
    def test_every_brand_has_every_card_position(self, week: int) -> None:
        """어퍼·미드·로우는 **세 브랜드 모두**에 있다 — 사용자 표가 그렇게 나눠져 있다."""
        for brand in Brand:
            for gender in Gender:
                filled = [
                    tier
                    for tier in RivalTier
                    if roster.pool_for(gender, tier, week, brand, SEED)
                ]
                assert len(filled) >= 2, f"{gender}/{brand} {week}주차: {filled}"

    @pytest.mark.parametrize("week", WEEKS)
    def test_only_developmental_starters_stand_in_nxt(self, week: int) -> None:
        """**콜업 전까지만 NXT다** — 위상이 아니라 출발점이 브랜드를 정한다."""
        for member in roster.active_at(week):
            if roster.brand_at(member, week, SEED) is Brand.NXT:
                assert member.develops

    def test_the_fold_is_a_no_op_now(self) -> None:
        """세 브랜드에 세 위상이 다 있으므로 접을 것이 없다 (§3-D95).

        함수는 남겨 둔다 — 부르는 자리가 열 곳이 넘고, 없는 칸이 다시 생기면 그
        판단이 여기 한 곳에 모여야 한다.
        """
        for brand in Brand:
            for tier in RivalTier:
                assert roster.tier_in(brand, tier) is tier

    def test_every_brand_keeps_people_for_thirty_years(self) -> None:
        """**바닥은 브랜드 전체로 잰다** (§3-D95 개정).

        칸 하나가 잠깐 비는 것은 이제 사고가 아니다 — 벨트는 한 칸 아래에서 도전자를
        찾고(§3-D95의 `UNDERDOG_SHARE`), 대립도 같은 길로 간다. 무너지면 안 되는 것은
        **브랜드에 사람이 남아 있는가**다.
        """
        for gender in Gender:
            for brand in Brand:
                for week in range(0, CAREER_WEEKS + 1, WEEKS_PER_YEAR):
                    people = sum(
                        len(roster.pool_for(gender, tier, week, brand, SEED))
                        for tier in RivalTier
                    )
                    assert people >= roster.MIN_BRAND_POOL, (
                        f"{gender}/{brand} {week // WEEKS_PER_YEAR}년차: {people}명"
                    )


class TestTheBeltStaysHome:
    @pytest.mark.parametrize("title", sorted(TITLES, key=lambda t: t.value))
    @pytest.mark.parametrize("week", WEEKS)
    def test_a_champion_stands_on_that_brand(self, title: Title, week: int) -> None:
        """**벨트는 자기 브랜드 사람에게서 시작한다** (§3-D53).

        재위 *도중*에 드래프트·트레이드로 브랜드를 옮기면 벨트는 그 사람을 따라간다
        (2026-08-19 확인). 실제 WWE도 그렇게 하고, 무엇보다 계보가 그 이동을 미리 알
        수 없다 — 계보가 브랜드를 묻고 브랜드가 드래프트를 묻는데, 드래프트는 그 주의
        챔피언을 보호하려고 다시 계보를 묻는다(`roster._trades`의 주석). 그래서 재위가
        **시작된 주차**로 잰다.
        """
        spec = TITLES[title]
        holder = title_scene.champion_at(SEED, week, title)
        assert holder is not None
        reigns = title_scene.reigns_upto(SEED, week, title)
        began = reigns[-1].start if reigns else week
        # 태그 벨트는 둘이 든다 (§3-D57) — 전원이 그 브랜드에서 시작해야 한다.
        for name in title_scene.members_of(holder):
            member = roster.member_of(name, SEED)
            assert member is not None
            if len(spec.brands) == 1:
                assert roster.brand_at(member, began, SEED) is next(iter(spec.brands))
            else:
                # 브랜드 통합 벨트(여성부 태그팀)는 메인 로스터 어느 쪽이어도 된다.
                assert roster.brand_at(member, began, SEED) in spec.brands

    @pytest.mark.parametrize("title", sorted(TITLES, key=lambda t: t.value))
    @pytest.mark.parametrize("week", WEEKS)
    def test_a_retired_wrestler_never_holds_a_belt(
        self, title: Title, week: int
    ) -> None:
        """은퇴한 사람이 벨트를 들고 있으면 명부의 시간 축이 무의미해진다 (§3-D13-1)."""
        holder = title_scene.champion_at(SEED, week, title)
        for name in title_scene.members_of(holder or ""):
            member = roster.member_of(name, SEED)
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
            for label in (match.left, match.right):
                for name in title_scene.members_of(label):
                    member = roster.member_of(name, SEED)
                    if member is None:
                        # 팀 이름이다 (§3-D62) — 사람이 아니라 조회되지 않는다.
                        # 그쪽의 브랜드는 `_title_bout`이 이름을 붙이기 전에 본다.
                        continue
                    assert roster.brand_at(member, week, SEED) is brand

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
        member = roster.member_of(rival, SEED)
        assert member is not None
        assert roster.brand_at(member, 300, SEED) is brand

    def test_the_titles_of_a_brand_are_that_brands(self) -> None:
        # 카드가 거는 벨트는 `titles_of(brand, gender)`가 정한다 — 여기가 어긋나면
        # 브랜드를 걸러도 남의 벨트가 그 밤에 걸린다.
        for brand in Brand:
            for gender in Gender:
                for title in titles_of(brand, gender):
                    assert brand in TITLES[title].brands
