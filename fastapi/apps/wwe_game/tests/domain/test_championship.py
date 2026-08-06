"""챔피언십 — 브랜드 · 계층 사다리 · 그랜드슬램 · NXT 콜업 (2026-08-06 스펙)."""

from __future__ import annotations

import pytest
from _helpers import make_run  # noqa: I001
from wwe_game.domain.exceptions import InvalidCareerRunError
from wwe_game.domain.services.championship import (
    DEFENSE_REWARD,
    NXT_CALLUP_POPULARITY,
    REPEAT_REWARD_FACTOR,
    award,
    call_up,
    draft,
    eligible_titles,
    grand_slam_chase,
    is_grand_slam,
    loss_of,
    other_brand,
    reward_of,
    should_call_up,
    slam_level,
    strip,
    target_title,
    title_shot_chance,
    title_win_chance,
    wants_transfer,
)
from wwe_game.domain.services.seeded_roll import SeededRoll
from wwe_game.domain.value_objects.title import (
    GRAND_SLAM_GROUPS,
    TITLES,
    Brand,
    Title,
    TitleTier,
    grand_slam_level,
    group_counts,
    missing_groups,
    nxt_titles,
    titles_of,
)
from wwe_game.domain.value_objects.wrestler_identity import Gender
from wwe_game.domain.value_objects.wrestler_stats import WrestlerStats

RAW_SWEEP = (
    Title.WORLD_HEAVYWEIGHT_CHAMPIONSHIP,
    Title.INTERCONTINENTAL_CHAMPIONSHIP,
    Title.WORLD_TAG_TEAM_CHAMPIONSHIP,
)


class TestBrandStructure:
    def test_nine_belts_across_three_brands(self) -> None:
        assert len(TITLES) == 17
        for brand in Brand:
            assert len(titles_of(brand, Gender.MALE)) == 3

    def test_each_brand_has_one_of_every_tier(self) -> None:
        for brand in Brand:
            tiers = [TITLES[t].tier for t in titles_of(brand, Gender.MALE)]
            assert set(tiers) == set(TitleTier)

    def test_titles_of_lists_top_tier_first(self) -> None:
        assert TITLES[titles_of(Brand.RAW, Gender.MALE)[0]].tier is TitleTier.WORLD

    def test_ic_is_raw_and_us_is_smackdown(self) -> None:
        # 그랜드슬램이 둘 다 요구하므로 브랜드 이동이 강제된다.
        assert TITLES[Title.INTERCONTINENTAL_CHAMPIONSHIP].brands == {Brand.RAW}
        assert TITLES[Title.UNITED_STATES_CHAMPIONSHIP].brands == {Brand.SMACKDOWN}


class TestOpportunityScalesWithPopularity:
    def test_more_popularity_means_more_shots(self) -> None:
        assert title_shot_chance(90) > title_shot_chance(50) > title_shot_chance(10)

    def test_tv_shots_are_rarer_than_ple_shots(self) -> None:
        assert title_shot_chance(60, on_tv=True) < title_shot_chance(60)
        assert title_shot_chance(60, on_tv=True) > 0.0


class TestTierLadder:
    @pytest.mark.parametrize(
        ("popularity", "expected"),
        [
            (0, None),
            (29, None),
            (30, Title.WORLD_TAG_TEAM_CHAMPIONSHIP),
            (50, Title.INTERCONTINENTAL_CHAMPIONSHIP),
            (80, Title.WORLD_HEAVYWEIGHT_CHAMPIONSHIP),
        ],
    )
    def test_highest_reachable_belt_on_your_brand(
        self, popularity: int, expected: Title | None
    ) -> None:
        run = make_run(brand=Brand.RAW, stats=WrestlerStats(popularity=popularity))
        assert target_title(run) is expected

    def test_smackdown_offers_different_belts(self) -> None:
        run = make_run(brand=Brand.SMACKDOWN, stats=WrestlerStats(popularity=55))
        assert target_title(run) is Title.UNITED_STATES_CHAMPIONSHIP

    def test_you_cannot_challenge_another_brands_belt(self) -> None:
        run = make_run(brand=Brand.RAW, stats=WrestlerStats(popularity=100))
        assert Title.UNITED_STATES_CHAMPIONSHIP not in eligible_titles(run)

    def test_falling_popularity_drops_you_down_the_ladder(self) -> None:
        run = make_run(brand=Brand.RAW, stats=WrestlerStats(popularity=85))
        assert target_title(run) is Title.WORLD_HEAVYWEIGHT_CHAMPIONSHIP
        cooled = run.evolve(stats=WrestlerStats(popularity=35))
        assert target_title(cooled) is Title.WORLD_TAG_TEAM_CHAMPIONSHIP


class TestGrandSlamGroups:
    def test_four_groups(self) -> None:
        assert [name for name, _ in GRAND_SLAM_GROUPS[Gender.MALE]] == [
            "월드",
            "인터컨티넨탈",
            "US",
            "태그팀",
        ]

    def test_world_group_accepts_either_belt(self) -> None:
        assert (
            grand_slam_level(
                (
                    Title.UNDISPUTED_WWE_CHAMPIONSHIP,
                    Title.INTERCONTINENTAL_CHAMPIONSHIP,
                    Title.UNITED_STATES_CHAMPIONSHIP,
                    Title.WWE_TAG_TEAM_CHAMPIONSHIP,
                ),
                Gender.MALE,
            )
            == 1
        )

    def test_ic_and_us_are_both_required(self) -> None:
        # 둘 다 2선이지만 서로를 대신하지 못한다.
        won = (
            Title.WORLD_HEAVYWEIGHT_CHAMPIONSHIP,
            Title.INTERCONTINENTAL_CHAMPIONSHIP,
            Title.INTERCONTINENTAL_CHAMPIONSHIP,
            Title.WWE_TAG_TEAM_CHAMPIONSHIP,
        )
        assert grand_slam_level(won, Gender.MALE) == 0
        assert missing_groups(won, Gender.MALE) == ("US",)

    def test_the_weakest_group_sets_the_level(self) -> None:
        won = (Title.WORLD_HEAVYWEIGHT_CHAMPIONSHIP,) * 5
        assert grand_slam_level(won, Gender.MALE) == 0
        assert group_counts(won, Gender.MALE)["월드"] == 5

    def test_double_grand_slam_needs_every_group_twice(self) -> None:
        single = (
            Title.WORLD_HEAVYWEIGHT_CHAMPIONSHIP,
            Title.INTERCONTINENTAL_CHAMPIONSHIP,
            Title.UNITED_STATES_CHAMPIONSHIP,
            Title.WWE_TAG_TEAM_CHAMPIONSHIP,
        )
        assert grand_slam_level(single, Gender.MALE) == 1
        assert grand_slam_level(single * 2, Gender.MALE) == 2

    def test_the_world_group_can_be_filled_by_two_different_belts(self) -> None:
        won = (
            Title.WORLD_HEAVYWEIGHT_CHAMPIONSHIP,
            Title.UNDISPUTED_WWE_CHAMPIONSHIP,
            Title.INTERCONTINENTAL_CHAMPIONSHIP,
            Title.INTERCONTINENTAL_CHAMPIONSHIP,
            Title.UNITED_STATES_CHAMPIONSHIP,
            Title.UNITED_STATES_CHAMPIONSHIP,
            Title.WWE_TAG_TEAM_CHAMPIONSHIP,
            Title.WORLD_TAG_TEAM_CHAMPIONSHIP,
        )
        assert grand_slam_level(won, Gender.MALE) == 2

    def test_nxt_belts_do_not_count(self) -> None:
        assert grand_slam_level(tuple(nxt_titles(Gender.MALE)) * 3, Gender.MALE) == 0


class TestGrandSlamPriority:
    def test_one_group_short_overrides_the_ladder(self) -> None:
        # RAW 최상위에 있어도 마지막 한 그룹이 태그면 태그를 노린다.
        run = make_run(
            brand=Brand.RAW,
            stats=WrestlerStats(popularity=95),
            titles_won=(
                Title.WORLD_HEAVYWEIGHT_CHAMPIONSHIP,
                Title.INTERCONTINENTAL_CHAMPIONSHIP,
                Title.UNITED_STATES_CHAMPIONSHIP,
            ),
        )
        assert grand_slam_chase(run) is Title.WORLD_TAG_TEAM_CHAMPIONSHIP
        assert target_title(run) is Title.WORLD_TAG_TEAM_CHAMPIONSHIP

    def test_two_groups_short_does_not_override(self) -> None:
        run = make_run(brand=Brand.RAW, stats=WrestlerStats(popularity=95))
        assert grand_slam_chase(run) is None
        assert target_title(run) is Title.WORLD_HEAVYWEIGHT_CHAMPIONSHIP

    def test_a_belt_on_the_other_brand_cannot_be_chased(self) -> None:
        run = make_run(
            brand=Brand.RAW,
            stats=WrestlerStats(popularity=95),
            titles_won=RAW_SWEEP,
        )
        assert missing_groups(run.titles_won, Gender.MALE) == ("US",)
        assert grand_slam_chase(run) is None  # US는 스맥다운에 있다
        assert wants_transfer(run)

    def test_nxt_never_chases_the_slam(self) -> None:
        run = make_run(brand=Brand.NXT, stats=WrestlerStats(popularity=45))
        assert grand_slam_chase(run) is None


class TestReignsAndDefenses:
    def test_a_new_reign_records_history(self) -> None:
        run = award(make_run(), Title.WORLD_TAG_TEAM_CHAMPIONSHIP)
        assert run.titles_held == {Title.WORLD_TAG_TEAM_CHAMPIONSHIP}
        assert run.won_count(Title.WORLD_TAG_TEAM_CHAMPIONSHIP) == 1

    def test_defending_does_not_add_a_reign(self) -> None:
        # 한 번 감고 서른 번 지킨 것과 서른 번 새로 감은 것은 다른 커리어다.
        run = award(make_run(), Title.WORLD_TAG_TEAM_CHAMPIONSHIP)
        again = award(run, Title.WORLD_TAG_TEAM_CHAMPIONSHIP)
        assert again.won_count(Title.WORLD_TAG_TEAM_CHAMPIONSHIP) == 1

    def test_regaining_after_losing_counts_twice(self) -> None:
        run = award(make_run(), Title.WORLD_TAG_TEAM_CHAMPIONSHIP)
        run = award(
            strip(run, Title.WORLD_TAG_TEAM_CHAMPIONSHIP),
            Title.WORLD_TAG_TEAM_CHAMPIONSHIP,
        )
        assert run.won_count(Title.WORLD_TAG_TEAM_CHAMPIONSHIP) == 2

    def test_losing_keeps_the_history(self) -> None:
        run = strip(
            award(make_run(), Title.INTERCONTINENTAL_CHAMPIONSHIP),
            Title.INTERCONTINENTAL_CHAMPIONSHIP,
        )
        assert run.titles_held == frozenset()
        assert run.won_count(Title.INTERCONTINENTAL_CHAMPIONSHIP) == 1

    def test_defense_pays_less_than_a_new_reign(self) -> None:
        first = reward_of(Title.WORLD_HEAVYWEIGHT_CHAMPIONSHIP)["popularity"]
        assert DEFENSE_REWARD["popularity"] < first
        assert DEFENSE_REWARD["popularity"] != DEFENSE_REWARD["in_ring"]

    def test_holding_a_belt_never_won_is_rejected(self) -> None:
        with pytest.raises(InvalidCareerRunError, match="획득 이력"):
            make_run(titles_held=frozenset({Title.WORLD_HEAVYWEIGHT_CHAMPIONSHIP}))

    def test_holding_another_brands_belt_is_rejected(self) -> None:
        with pytest.raises(InvalidCareerRunError, match="소속·디비전이 아닌"):
            make_run(
                brand=Brand.RAW,
                titles_won=(Title.UNITED_STATES_CHAMPIONSHIP,),
                titles_held=frozenset({Title.UNITED_STATES_CHAMPIONSHIP}),
            )


class TestRewards:
    @pytest.mark.parametrize("title", list(Title))
    def test_popularity_and_in_ring_rewards_always_differ(self, title: Title) -> None:
        r = reward_of(title)
        assert r["popularity"] > r["in_ring"]  # 벨트는 실력보다 명성을 키운다

    def test_main_roster_world_pays_more_than_nxt_world(self) -> None:
        assert (
            reward_of(Title.WORLD_HEAVYWEIGHT_CHAMPIONSHIP)["popularity"]
            > reward_of(Title.NXT_CHAMPIONSHIP)["popularity"]
        )

    def test_repeat_reigns_reward_less(self) -> None:
        first = reward_of(Title.WORLD_HEAVYWEIGHT_CHAMPIONSHIP)["popularity"]
        again = reward_of(Title.WORLD_HEAVYWEIGHT_CHAMPIONSHIP, first_time=False)[
            "popularity"
        ]
        assert again == round(first * REPEAT_REWARD_FACTOR) < first

    def test_losing_a_world_belt_hurts_most(self) -> None:
        assert (
            loss_of(Title.WORLD_HEAVYWEIGHT_CHAMPIONSHIP)["popularity"]
            < loss_of(Title.WORLD_TAG_TEAM_CHAMPIONSHIP)["popularity"]
        )


class TestTitleMatchOdds:
    def test_a_stronger_wrestler_is_likelier_to_win(self) -> None:
        w = Title.WORLD_HEAVYWEIGHT_CHAMPIONSHIP
        assert title_win_chance(90, w) > title_win_chance(40, w)

    def test_the_world_belt_is_harder_than_nxt(self) -> None:
        assert title_win_chance(60, Title.WORLD_HEAVYWEIGHT_CHAMPIONSHIP) < (
            title_win_chance(60, Title.NXT_CHAMPIONSHIP)
        )


class TestCallUp:
    def test_starts_in_nxt(self) -> None:
        from wwe_game.domain.entities.career_run import start_run
        from wwe_game.domain.value_objects.game_mode import game_mode_of

        run = start_run(
            identity=make_run().identity, mode=game_mode_of("weekly"), seed=1
        )
        assert run.brand is Brand.NXT

    def test_popularity_threshold_triggers_the_call_up(self) -> None:
        below = make_run(
            brand=Brand.NXT,
            stats=WrestlerStats(popularity=NXT_CALLUP_POPULARITY - 1),
        )
        at = make_run(
            brand=Brand.NXT, stats=WrestlerStats(popularity=NXT_CALLUP_POPULARITY)
        )
        assert not should_call_up(below)
        assert should_call_up(at)

    def test_sweeping_every_nxt_belt_triggers_the_call_up(self) -> None:
        run = make_run(
            brand=Brand.NXT,
            stats=WrestlerStats(popularity=20),
            titles_won=tuple(nxt_titles(Gender.MALE)),
        )
        assert should_call_up(run)

    def test_main_roster_never_calls_up_again(self) -> None:
        assert not should_call_up(
            make_run(brand=Brand.RAW, stats=WrestlerStats(popularity=100))
        )

    def test_call_up_halves_popularity_and_vacates_nxt_belts(self) -> None:
        run = make_run(
            brand=Brand.NXT,
            stats=WrestlerStats(popularity=60),
            titles_won=(Title.NXT_CHAMPIONSHIP,),
            titles_held=frozenset({Title.NXT_CHAMPIONSHIP}),
        )
        promoted = call_up(run, SeededRoll(1, 1, "brand"))
        assert promoted.brand in {Brand.RAW, Brand.SMACKDOWN}
        assert promoted.stats.popularity == 30
        assert promoted.titles_held == frozenset()
        # 이력은 남는다 — NXT 챔피언이었다는 사실은 지워지지 않는다
        assert promoted.won_count(Title.NXT_CHAMPIONSHIP) == 1


class TestDraft:
    def test_draft_moves_you_to_the_other_brand(self) -> None:
        run = make_run(brand=Brand.RAW)
        moved = draft(run, SeededRoll(1, 1, "always"))
        assert moved.brand in {Brand.RAW, Brand.SMACKDOWN}

    def test_nxt_is_not_in_the_draft(self) -> None:
        run = make_run(brand=Brand.NXT)
        assert draft(run, SeededRoll(1, 1, "brand")).brand is Brand.NXT

    def test_moving_brands_vacates_belts_left_behind(self) -> None:
        run = make_run(
            brand=Brand.RAW,
            titles_won=(Title.INTERCONTINENTAL_CHAMPIONSHIP,),
            titles_held=frozenset({Title.INTERCONTINENTAL_CHAMPIONSHIP}),
        )
        for seed in range(40):
            moved = draft(run, SeededRoll(seed, 1, "brand"))
            if moved.brand is Brand.SMACKDOWN:
                assert moved.titles_held == frozenset()
                return
        pytest.fail("40번 굴려도 드래프트가 한 번도 안 일어났다")

    def test_chasing_a_belt_on_the_other_brand_raises_the_odds(self) -> None:
        chasing = make_run(brand=Brand.RAW, titles_won=RAW_SWEEP)
        settled = make_run(
            brand=Brand.RAW,
            titles_won=(*RAW_SWEEP, Title.UNITED_STATES_CHAMPIONSHIP),
        )
        assert wants_transfer(chasing)
        assert not wants_transfer(settled)

    def test_other_brand_flips(self) -> None:
        assert other_brand(Brand.RAW) is Brand.SMACKDOWN
        assert other_brand(Brand.SMACKDOWN) is Brand.RAW


class TestSlamHelpers:
    def test_slam_level_reads_the_run(self) -> None:
        run = make_run(
            titles_won=(
                Title.WORLD_HEAVYWEIGHT_CHAMPIONSHIP,
                Title.INTERCONTINENTAL_CHAMPIONSHIP,
                Title.UNITED_STATES_CHAMPIONSHIP,
                Title.WORLD_TAG_TEAM_CHAMPIONSHIP,
            )
        )
        assert slam_level(run) == 1
        assert is_grand_slam(run)

    def test_no_belts_is_no_slam(self) -> None:
        assert not is_grand_slam(make_run())


class TestWomensDivision:
    def test_nine_mens_belts_and_eight_womens(self) -> None:
        # 여성부 태그팀이 브랜드 통합이라 하나뿐이다 (스펙).
        male = [s for s in TITLES.values() if s.gender is Gender.MALE]
        female = [s for s in TITLES.values() if s.gender is Gender.FEMALE]
        assert (len(male), len(female)) == (9, 8)

    def test_every_belt_has_a_distinct_display_name(self) -> None:
        names = [s.display_name for s in TITLES.values()]
        assert len(set(names)) == len(names)
        assert all(names)

    def test_womens_tag_team_is_unified_across_both_shows(self) -> None:
        spec = TITLES[Title.WWE_WOMENS_TAG_TEAM_CHAMPIONSHIP]
        assert spec.brands == {Brand.RAW, Brand.SMACKDOWN}

    def test_mens_tag_team_belts_are_brand_specific(self) -> None:
        assert TITLES[Title.WORLD_TAG_TEAM_CHAMPIONSHIP].brands == {Brand.RAW}
        assert TITLES[Title.WWE_TAG_TEAM_CHAMPIONSHIP].brands == {Brand.SMACKDOWN}

    def test_a_woman_can_chase_the_tag_belt_on_either_show(self) -> None:
        for brand in (Brand.RAW, Brand.SMACKDOWN):
            run = make_run(
                gender=Gender.FEMALE, brand=brand, stats=WrestlerStats(popularity=35)
            )
            assert target_title(run) is Title.WWE_WOMENS_TAG_TEAM_CHAMPIONSHIP

    def test_divisions_never_see_each_others_belts(self) -> None:
        for brand in Brand:
            male = set(titles_of(brand, Gender.MALE))
            female = set(titles_of(brand, Gender.FEMALE))
            assert male.isdisjoint(female)

    def test_womens_grand_slam_uses_womens_belts(self) -> None:
        won = (
            Title.WOMENS_WORLD_CHAMPIONSHIP,
            Title.WWE_WOMENS_INTERCONTINENTAL_CHAMPIONSHIP,
            Title.WWE_WOMENS_UNITED_STATES_CHAMPIONSHIP,
            Title.WWE_WOMENS_TAG_TEAM_CHAMPIONSHIP,
        )
        assert grand_slam_level(won, Gender.FEMALE) == 1
        assert grand_slam_level(won, Gender.MALE) == 0

    def test_mens_belts_do_not_count_for_a_woman(self) -> None:
        mens = (
            Title.WORLD_HEAVYWEIGHT_CHAMPIONSHIP,
            Title.INTERCONTINENTAL_CHAMPIONSHIP,
            Title.UNITED_STATES_CHAMPIONSHIP,
            Title.WORLD_TAG_TEAM_CHAMPIONSHIP,
        )
        assert grand_slam_level(mens, Gender.FEMALE) == 0

    def test_nxt_womens_route_climbs_north_american_first(self) -> None:
        # 스펙의 계단식 루트: 노스 아메리칸(25) → NXT 위민스(40)
        early = make_run(
            gender=Gender.FEMALE, brand=Brand.NXT, stats=WrestlerStats(popularity=30)
        )
        later = make_run(
            gender=Gender.FEMALE, brand=Brand.NXT, stats=WrestlerStats(popularity=45)
        )
        assert target_title(early) is Title.NXT_WOMENS_NORTH_AMERICAN_CHAMPIONSHIP
        assert target_title(later) is Title.NXT_WOMENS_CHAMPIONSHIP

    def test_a_woman_called_up_vacates_nxt_womens_belts(self) -> None:
        run = make_run(
            gender=Gender.FEMALE,
            brand=Brand.NXT,
            stats=WrestlerStats(popularity=60),
            titles_won=(Title.NXT_WOMENS_CHAMPIONSHIP,),
            titles_held=frozenset({Title.NXT_WOMENS_CHAMPIONSHIP}),
        )
        promoted = call_up(run, SeededRoll(1, 1, "brand"))
        assert promoted.titles_held == frozenset()
        assert promoted.won_count(Title.NXT_WOMENS_CHAMPIONSHIP) == 1
