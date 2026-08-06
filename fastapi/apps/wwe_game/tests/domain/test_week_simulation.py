"""T3 주차 시뮬 — 시드 결정성 · 나이 곡선 · 인기도 우선 · 부상 회복."""

from __future__ import annotations

import pytest
from _helpers import make_run  # noqa: I001  (tests 트리에 __init__.py가 없다)
from wwe_game.domain.constants import career_rules as rules
from wwe_game.domain.services.seeded_roll import SeededRoll
from wwe_game.domain.services.week_simulation import (
    age_penalty,
    alignment_clarity,
    apply_week,
    injury_chance,
    performance_score,
    popularity_decay_chance,
    raw_age_penalty,
    simulate_week,
    week_kind_of,
    win_chance,
)
from wwe_game.domain.value_objects.condition import Condition, InjuryGrade
from wwe_game.domain.value_objects.title import Brand, Title
from wwe_game.domain.value_objects.week_report import WeekKind
from wwe_game.domain.value_objects.wrestler_identity import PlayStyle
from wwe_game.domain.value_objects.wrestler_stats import WrestlerStats

# ── 시드 결정성 ──────────────────────────────────────────────


class TestDeterminism:
    def test_same_seed_same_week_gives_identical_report(self) -> None:
        a = simulate_week(make_run(seed=7, week=100))
        b = simulate_week(make_run(seed=7, week=100))
        assert a == b

    def test_different_seed_diverges(self) -> None:
        reports_a = [simulate_week(make_run(seed=1, week=w)) for w in range(60)]
        reports_b = [simulate_week(make_run(seed=2, week=w)) for w in range(60)]
        assert reports_a != reports_b

    def test_a_full_run_replays_identically(self) -> None:
        def play(seed: int, weeks: int) -> list[object]:
            run = make_run(seed=seed)
            trail: list[object] = []
            for _ in range(weeks):
                report = simulate_week(run)
                trail.append(report)
                run = apply_week(run, report)
            return trail

        assert play(99, 200) == play(99, 200)

    def test_roll_is_stable_across_processes(self) -> None:
        # 파이썬 `hash()`는 프로세스마다 소금값이 달라 재현이 깨진다. blake2b로 고정했으므로
        # 값 자체가 리터럴로 박혀 있어야 한다.
        assert SeededRoll(42, 10, "match").between(0, 10**6) == 184564

    def test_channels_are_independent(self) -> None:
        a = SeededRoll(1, 1, "match").between(0, 10**6)
        b = SeededRoll(1, 1, "injury").between(0, 10**6)
        assert a != b


# ── 나이 곡선과 인기도 우선 ──────────────────────────────────


class TestAgeCurve:
    @pytest.mark.parametrize(
        ("age", "expected"),
        [(20, 0.0), (25, 0.0), (34, 0.0), (35, 0.04), (42, 0.32), (43, 0.40)],
    )
    def test_raw_penalty_by_band(self, age: int, expected: float) -> None:
        assert raw_age_penalty(age) == pytest.approx(expected)

    def test_penalty_is_capped(self) -> None:
        assert raw_age_penalty(50) == rules.AGE_PENALTY_CAP
        assert raw_age_penalty(99) == rules.AGE_PENALTY_CAP

    def test_popularity_erases_most_of_the_age_penalty(self) -> None:
        # 같은 50세라도 인기도가 결과를 가른다 — 사용자 결정의 핵심.
        unpopular = age_penalty(50, popularity=10)
        popular = age_penalty(50, popularity=100)
        assert popular < unpopular
        assert popular == pytest.approx(rules.AGE_PENALTY_CAP * 0.20)
        assert unpopular == pytest.approx(rules.AGE_PENALTY_CAP * 0.92)

    def test_popularity_cannot_erase_penalty_entirely(self) -> None:
        assert age_penalty(50, popularity=100) > 0.0

    def test_young_wrestler_has_no_penalty_regardless_of_popularity(self) -> None:
        assert age_penalty(30, popularity=0) == 0.0


class TestPopularityOutranksAge:
    def test_popular_veteran_beats_unpopular_youngster(self) -> None:
        veteran = performance_score(
            WrestlerStats(popularity=85, in_ring=50, mic_work=70), Condition(), age=48
        )
        youngster = performance_score(
            WrestlerStats(popularity=15, in_ring=70, mic_work=30), Condition(), age=27
        )
        assert veteran > youngster

    def test_popularity_weighs_more_than_in_ring(self) -> None:
        by_popularity = performance_score(
            WrestlerStats(popularity=80, in_ring=20), Condition(), age=30
        )
        by_skill = performance_score(
            WrestlerStats(popularity=20, in_ring=80), Condition(), age=30
        )
        assert by_popularity > by_skill

    def test_weights_put_popularity_first(self) -> None:
        assert rules.WEIGHT_POPULARITY > rules.WEIGHT_IN_RING > rules.WEIGHT_MIC_WORK

    def test_win_chance_stays_within_bounds(self) -> None:
        assert win_chance(0.0) == rules.WIN_CHANCE_FLOOR
        assert win_chance(100.0) == rules.WIN_CHANCE_CEILING
        assert rules.WIN_CHANCE_FLOOR <= win_chance(55.0) <= rules.WIN_CHANCE_CEILING

    def test_act_four_is_delayed_for_popular_wrestlers(self) -> None:
        popular = make_run(week=24 * 52, stats=WrestlerStats(popularity=70))
        washed_up = make_run(week=24 * 52, stats=WrestlerStats(popularity=20))
        assert popular.age == washed_up.age == 44
        assert popular.act == 3  # 인기도 60+ 는 47세까지 메인이벤터
        assert washed_up.act == 4


# ── 주차 종류 ────────────────────────────────────────────────


class TestWeekKind:
    def test_every_thirteenth_week_is_a_ple(self) -> None:
        assert week_kind_of(make_run(week=12)) is WeekKind.PLE
        assert week_kind_of(make_run(week=25)) is WeekKind.PLE
        assert week_kind_of(make_run(week=11)) is WeekKind.WEEKLY_SHOW

    def test_injured_weeks_are_off_weeks(self) -> None:
        hurt = make_run(week=12, condition=Condition().injured(InjuryGrade.MINOR, 4))
        assert week_kind_of(hurt) is WeekKind.OFF

    def test_off_week_has_no_match_and_repays_wear(self) -> None:
        hurt = make_run(
            condition=Condition(wear=30).injured(InjuryGrade.SERIOUS, 12),
        )
        report = simulate_week(hurt)
        assert report.kind is WeekKind.OFF
        assert not report.had_match
        assert report.wear_delta == -rules.WEAR_RECOVERY_PER_OFF_WEEK


# ── 부상 ─────────────────────────────────────────────────────


class TestInjury:
    def test_off_weeks_carry_no_injury_risk(self) -> None:
        hurt = make_run(condition=Condition().injured(InjuryGrade.MINOR, 3))
        assert injury_chance(hurt, WeekKind.OFF) == 0.0

    def test_wear_raises_injury_risk(self) -> None:
        fresh = make_run(condition=Condition(wear=0))
        worn = make_run(condition=Condition(wear=100))
        assert injury_chance(worn, WeekKind.WEEKLY_SHOW) > injury_chance(
            fresh, WeekKind.WEEKLY_SHOW
        )

    def test_high_flyer_is_riskier_than_technician(self) -> None:
        flyer = make_run(style=PlayStyle.HIGH_FLYER)
        tech = make_run(style=PlayStyle.TECHNICIAN)
        assert injury_chance(flyer, WeekKind.WEEKLY_SHOW) > injury_chance(
            tech, WeekKind.WEEKLY_SHOW
        )

    def test_ple_is_riskier_than_a_weekly_show(self) -> None:
        run = make_run()
        assert injury_chance(run, WeekKind.PLE) > injury_chance(
            run, WeekKind.WEEKLY_SHOW
        )

    def test_recovery_counts_down_and_heals(self) -> None:
        run = make_run(condition=Condition().injured(InjuryGrade.MINOR, 3))
        for _ in range(3):
            run = apply_week(run, simulate_week(run))
        assert not run.condition.is_injured


# ── 반영 ─────────────────────────────────────────────────────


class TestApplyWeek:
    def test_week_advances_by_one(self) -> None:
        run = make_run(week=40)
        assert apply_week(run, simulate_week(run)).week == 41

    def test_mismatched_report_is_rejected(self) -> None:
        run = make_run(week=40)
        report = simulate_week(make_run(week=90))
        with pytest.raises(ValueError, match="어긋납니다"):
            apply_week(run, report)

    def test_stats_never_leave_their_range_over_a_long_run(self) -> None:
        run = make_run(seed=3)
        for _ in range(600):
            run = apply_week(run, simulate_week(run))
        s = run.stats
        assert 0 <= s.popularity <= 100
        assert 0 <= s.in_ring <= 100
        assert 0 <= s.mic_work <= 100
        assert 0 <= run.condition.wear <= 100

    def test_growth_diminishes_instead_of_pinning_at_100(self) -> None:
        # 고정 확률이면 1560주에 전부 100에 붙는다. 체감 곡선이 그걸 막는지 본다.
        run = make_run(seed=11)
        for _ in range(1200):
            run = apply_week(run, simulate_week(run))
        assert run.stats.in_ring < 100


# ── 인기도 망각 ──────────────────────────────────────────────


class TestPopularityDecay:
    def test_decay_scales_with_current_popularity(self) -> None:
        # 높이 오를수록 유지 비용이 크다.
        low = popularity_decay_chance(10, off_week=False)
        high = popularity_decay_chance(90, off_week=False)
        assert high > low > 0.0

    def test_nobody_at_zero_popularity_decays(self) -> None:
        assert popularity_decay_chance(0, off_week=False) == 0.0

    def test_being_out_of_sight_speeds_up_forgetting(self) -> None:
        assert popularity_decay_chance(50, off_week=True) > popularity_decay_chance(
            50, off_week=False
        )

    def test_off_weeks_can_only_lose_popularity(self) -> None:
        run = make_run(
            seed=5,
            stats=WrestlerStats(popularity=90),
            condition=Condition().injured(InjuryGrade.SERIOUS, 20),
        )
        deltas = [simulate_week(run.evolve(week=w)).stat_delta for w in range(60)]
        changes = [d["popularity"] for d in deltas if "popularity" in d]
        assert changes, "60주 동안 한 번도 안 식으면 망각 규칙이 안 걸린 것이다"
        assert all(c == -1 for c in changes)

    def test_popularity_reaches_an_equilibrium_instead_of_pinning_at_100(self) -> None:
        run = make_run(seed=21)
        for _ in range(1200):
            run = apply_week(run, simulate_week(run))
        assert 20 < run.stats.popularity < 90


# ── 마모 ─────────────────────────────────────────────────────


class TestWear:
    def test_wear_accumulates_but_stays_far_from_the_cap(self) -> None:
        # 경기마다 +1로 두었더니 100에 붙어 부상 악순환이 났다. 확률형으로 바꾼 이유.
        run = make_run(seed=13, style=PlayStyle.TECHNICIAN)
        for _ in range(1200):
            run = apply_week(run, simulate_week(run))
        assert 0 < run.condition.wear < 90

    def test_high_flyer_wears_faster_than_technician(self) -> None:
        # 최종 마모로 비교하면 안 된다 — 하이플라이어는 더 자주 다치고, 결장 주차가
        # 마모를 갚아 두 값이 수렴한다. 발생률 자체를 본다.
        def wear_gained(style: PlayStyle) -> int:
            run = make_run(seed=13, style=style)
            return sum(simulate_week(run.evolve(week=w)).wear_delta for w in range(800))

        assert wear_gained(PlayStyle.HIGH_FLYER) > wear_gained(PlayStyle.TECHNICIAN)

    def test_ple_weeks_wear_more_than_shows(self) -> None:
        run = make_run(style=PlayStyle.TECHNICIAN)
        ple = sum(
            simulate_week(run.evolve(week=w * 13 - 1)).wear_delta for w in range(1, 40)
        )
        show = sum(
            simulate_week(run.evolve(week=w)).wear_delta for w in range(1, 40) if w % 13
        )
        assert ple > show


# ── 편성: PLE는 반드시 경기, 주간은 갈린다 ───────────────────


class TestCardScheduling:
    def test_ple_always_has_a_match(self) -> None:
        # 스펙: PLE는 경기가 있어야 한다.
        for seed in range(30):
            run = make_run(seed=seed, week=rules.PLE_INTERVAL_WEEKS - 1)
            report = simulate_week(run)
            assert report.kind is WeekKind.PLE
            assert report.had_match

    def test_weekly_tv_is_sometimes_a_buildup_week(self) -> None:
        kinds = {simulate_week(make_run(seed=3, week=w)).kind for w in range(1, 60)}
        assert WeekKind.WEEKLY_SHOW in kinds
        assert WeekKind.PROMO in kinds

    def test_buildup_weeks_have_no_match_no_wear_no_injury(self) -> None:
        promo = next(
            r
            for w in range(1, 80)
            if (r := simulate_week(make_run(seed=3, week=w))).kind is WeekKind.PROMO
        )
        assert not promo.had_match
        assert promo.wear_delta == 0
        assert promo.injury is None

    def test_buildup_weeks_can_grow_mic_work(self) -> None:
        gained = [
            simulate_week(make_run(seed=s, week=w)).stat_delta.get("mic_work", 0)
            for s in range(6)
            for w in range(1, 60)
        ]
        assert sum(gained) > 0

    def test_injury_keeps_you_off_the_card_even_on_a_ple_week(self) -> None:
        hurt = make_run(
            week=rules.PLE_INTERVAL_WEEKS - 1,
            condition=Condition().injured(InjuryGrade.SERIOUS, 10),
        )
        assert simulate_week(hurt).kind is WeekKind.OFF


class TestTitleMatchPlacement:
    def test_title_matches_happen_at_ples(self) -> None:
        found = any(
            simulate_week(
                make_run(
                    seed=s,
                    week=rules.PLE_INTERVAL_WEEKS * k - 1,
                    stats=WrestlerStats(popularity=85),
                )
            ).is_title_match
            for s in range(8)
            for k in range(1, 12)
        )
        assert found

    def test_title_matches_also_happen_on_tv_but_rarely(self) -> None:
        ple = tv = 0
        for s in range(20):
            for w in range(1, 400):
                r = simulate_week(
                    make_run(seed=s, week=w, stats=WrestlerStats(popularity=85))
                )
                if r.is_title_match:
                    if r.kind is WeekKind.PLE:
                        ple += 1
                    elif r.kind is WeekKind.WEEKLY_SHOW:
                        tv += 1
        assert tv > 0, "TV 타이틀전이 한 번도 안 열렸다"
        assert tv < ple, "TV가 PLE보다 잦으면 PLE가 특별할 이유가 없다"

    def test_buildup_weeks_never_carry_a_title_match(self) -> None:
        assert all(
            not r.is_title_match
            for w in range(1, 200)
            if (
                r := simulate_week(
                    make_run(seed=9, week=w, stats=WrestlerStats(popularity=90))
                )
            ).kind
            is WeekKind.PROMO
        )


class TestBrandProgression:
    def test_a_career_starts_in_nxt_and_gets_called_up(self) -> None:
        run = make_run(brand=Brand.NXT, stats=WrestlerStats())
        for _ in range(700):
            run = apply_week(run, simulate_week(run))
            if run.brand is not Brand.NXT:
                break
        assert run.brand in {Brand.RAW, Brand.SMACKDOWN}, "700주 안에 콜업되지 않았다"

    def test_call_up_is_reported_on_the_week_it_happens(self) -> None:
        run = make_run(brand=Brand.NXT, stats=WrestlerStats())
        for _ in range(700):
            report = simulate_week(run)
            run = apply_week(run, report)
            if report.called_up:
                assert run.brand in {Brand.RAW, Brand.SMACKDOWN}
                return
        pytest.fail("콜업 리포트가 나오지 않았다")

    def test_draft_only_fires_on_draft_weeks(self) -> None:
        from wwe_game.domain.services.championship import DRAFT_INTERVAL_WEEKS

        for w in range(1, 120):
            report = simulate_week(make_run(seed=4, week=w))
            assert report.drafted == (report.week % DRAFT_INTERVAL_WEEKS == 0)

    def test_you_never_hold_a_belt_from_a_brand_you_left(self) -> None:
        # 불변식이 애그리거트에 있으므로 30년을 돌려 한 번도 안 깨지는지 본다.
        run = make_run(brand=Brand.NXT, stats=WrestlerStats(), seed=17)
        while run.is_active and run.week < 1560:
            run = apply_week(run, simulate_week(run))


class TestChampionsStayOver:
    def test_holding_a_belt_slows_forgetting(self) -> None:
        plain = popularity_decay_chance(70, off_week=False)
        champ = popularity_decay_chance(
            70,
            off_week=False,
            held=frozenset({Title.WORLD_HEAVYWEIGHT_CHAMPIONSHIP}),
        )
        assert champ < plain

    def test_a_world_belt_protects_more_than_a_tag_belt(self) -> None:
        world = popularity_decay_chance(
            70, off_week=False, held=frozenset({Title.WORLD_HEAVYWEIGHT_CHAMPIONSHIP})
        )
        tag = popularity_decay_chance(
            70, off_week=False, held=frozenset({Title.WORLD_TAG_TEAM_CHAMPIONSHIP})
        )
        assert world < tag

    def test_the_highest_belt_held_sets_the_relief(self) -> None:
        both = popularity_decay_chance(
            70,
            off_week=False,
            held=frozenset(
                {
                    Title.WORLD_HEAVYWEIGHT_CHAMPIONSHIP,
                    Title.WORLD_TAG_TEAM_CHAMPIONSHIP,
                }
            ),
        )
        world_only = popularity_decay_chance(
            70, off_week=False, held=frozenset({Title.WORLD_HEAVYWEIGHT_CHAMPIONSHIP})
        )
        assert both == world_only

    def test_relief_still_leaves_some_decay(self) -> None:
        assert (
            popularity_decay_chance(
                90,
                off_week=False,
                held=frozenset({Title.WORLD_HEAVYWEIGHT_CHAMPIONSHIP}),
            )
            > 0.0
        )


class TestAlignmentClarity:
    """뚜렷한 캐릭터가 인기도를 끌어올린다 — 부호가 아니라 절댓값을 본다."""

    def test_a_bland_character_gets_no_bonus(self) -> None:
        assert alignment_clarity(0) == 1.0

    def test_a_strong_heel_and_a_strong_face_are_worth_the_same(self) -> None:
        assert alignment_clarity(-80) == alignment_clarity(80)

    def test_clearer_is_better(self) -> None:
        assert alignment_clarity(100) > alignment_clarity(50) > alignment_clarity(10)

    def test_the_bonus_is_capped_by_the_alignment_range(self) -> None:
        assert alignment_clarity(100) == 1.0 + rules.ALIGNMENT_CLARITY_BONUS

    def test_a_vivid_character_gains_popularity_faster(self) -> None:
        def gains(alignment: int) -> int:
            run = make_run(
                seed=8, stats=WrestlerStats(popularity=30, alignment=alignment)
            )
            return sum(
                simulate_week(run.evolve(week=w)).stat_delta.get("popularity", 0)
                for w in range(400)
            )

        assert gains(90) > gains(0)
