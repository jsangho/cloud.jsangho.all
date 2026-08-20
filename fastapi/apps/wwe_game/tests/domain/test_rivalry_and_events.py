"""T4 대립 엔진 + T5 덱 로더·추첨."""

from __future__ import annotations

import pytest
from _helpers import make_run  # noqa: I001
from wwe_game.domain.constants import roster
from wwe_game.domain.constants.career_clock import WEEKS_PER_YEAR
from wwe_game.domain.constants.event_deck import BY_CODE, DECK, Arena, CardKind
from wwe_game.domain.entities.career_run import Rivalry, RivalryStage
from wwe_game.domain.services import championship, event_draw, rivalry_engine
from wwe_game.domain.services.seeded_roll import SeededRoll
from wwe_game.domain.value_objects.condition import Condition, InjuryGrade
from wwe_game.domain.value_objects.title import Brand
from wwe_game.domain.value_objects.wrestler_identity import Gender, PlayStyle
from wwe_game.domain.value_objects.wrestler_stats import WrestlerStats


def rival(name: str = "숙적", heat: int = 10, week: int = 0) -> Rivalry:
    return Rivalry(
        rival_name=name,
        stage=rivalry_engine.stage_for(heat),
        heat=heat,
        started_week=week,
    )


# ── T4 대립 ──────────────────────────────────────────────────


class TestRivalryStages:
    @pytest.mark.parametrize(
        ("heat", "expected"),
        [
            (0, RivalryStage.INDIFFERENT),
            (34, RivalryStage.INDIFFERENT),
            (35, RivalryStage.HEATED),
            (69, RivalryStage.HEATED),
            (70, RivalryStage.NEMESIS),
            (100, RivalryStage.NEMESIS),
        ],
    )
    def test_stage_is_derived_from_heat(
        self, heat: int, expected: RivalryStage
    ) -> None:
        assert rivalry_engine.stage_for(heat) is expected

    def test_heat_is_clamped(self) -> None:
        assert rivalry_engine.with_heat(rival(heat=95), 50).heat == 100
        assert rivalry_engine.with_heat(rival(heat=5), -50).heat == 0

    def test_stage_follows_heat_back_down(self) -> None:
        # 한 방향으로만 흐르면 모든 판이 같은 모양이 된다 (§5).
        hot = rivalry_engine.with_heat(rival(heat=40), 40)
        assert hot.stage is RivalryStage.NEMESIS
        assert rivalry_engine.with_heat(hot, -60).stage is RivalryStage.INDIFFERENT


class TestRivalryFlow:
    def test_only_the_hottest_rivalry_grows(self) -> None:
        run = make_run(rivalries=(rival("A", 50), rival("B", 20)))
        moved = {
            r.rival_name: r.heat
            for r in rivalry_engine.advance_rivalries(
                run, 10, 8, SeededRoll(1, 10, "riv")
            )
        }
        assert moved["A"] == 58
        assert moved["B"] == 20 - rivalry_engine.COOL_PER_QUIET_WEEK

    def test_a_cold_rivalry_is_dropped(self) -> None:
        run = make_run(rivalries=(rival("A", 60), rival("B", 1)))
        names = {
            r.rival_name
            for r in rivalry_engine.advance_rivalries(
                run, 10, 5, SeededRoll(1, 10, "riv")
            )
        }
        assert "B" not in names

    def test_a_ple_blow_off_settles_a_nemesis(self) -> None:
        run = make_run(rivalries=(rival("A", 90),))
        after = rivalry_engine.advance_rivalries(
            run, 13, 9, SeededRoll(1, 13, "riv"), blowoff=True
        )
        assert after[0].heat == 90 - rivalry_engine.BLOWOFF_HEAT_DROP
        assert after[0].stage is not RivalryStage.NEMESIS

    def test_a_blow_off_only_settles_a_nemesis(self) -> None:
        run = make_run(rivalries=(rival("A", 40),))
        after = rivalry_engine.advance_rivalries(
            run, 13, 9, SeededRoll(1, 13, "riv"), blowoff=True
        )
        assert after[0].heat > 40

    def test_never_more_than_two_active_rivalries(self) -> None:
        run = make_run(rivalries=(rival("A", 50), rival("B", 40)))
        for week in range(120):
            run = run.evolve(
                rivalries=rivalry_engine.advance_rivalries(
                    run, week, 3, SeededRoll(7, week, "riv")
                )
            )
            assert len(run.rivalries) <= rivalry_engine.MAX_ACTIVE


class TestRivalPool:
    def test_rivals_match_the_players_division(self) -> None:
        for gender in Gender:
            for tier in roster.RivalTier:
                names = roster.pool_for(gender, tier)
                assert names
                assert all(m.gender is gender for m in roster.ROSTER if m.name in names)

    def test_opponent_tier_follows_popularity(self) -> None:
        assert roster.tier_for_popularity(10) is roster.RivalTier.LOW_CARD
        assert roster.tier_for_popularity(40) is roster.RivalTier.MID_CARD
        assert roster.tier_for_popularity(80) is roster.RivalTier.UPPER_CARD

    def test_a_woman_never_feuds_with_a_man(self) -> None:
        run = make_run(gender=Gender.FEMALE, stats=WrestlerStats(popularity=70))
        womens = {m.name for m in roster.ROSTER if m.gender is Gender.FEMALE}
        for seed in range(30):
            name = rivalry_engine.pick_rival(run, SeededRoll(seed, 1, "riv"))
            assert name in womens

    def test_todays_roster_does_not_wrestle_forever(self) -> None:
        # 30년이면 로스터가 통째로 갈린다 — 오늘의 얼굴이 남아 있으면 안 된다.
        today = {m.name for m in roster.active_at(0)}
        late = {m.name for m in roster.active_at(30 * WEEKS_PER_YEAR)}
        assert not (today & late)

    def test_new_faces_debut_over_the_years(self) -> None:
        assert roster.active_at(0) != roster.active_at(10 * WEEKS_PER_YEAR)
        for year in (0, 10, 20, 30):
            assert len(roster.active_at(year * WEEKS_PER_YEAR)) >= 100

    def test_the_development_brand_arrives_later(self) -> None:
        # Evolve는 NXT 아래 단계라 몇 해 뒤에 올라온다 (2026-08-07 사용자 요청).
        evolve = {"아론 루크", "제나 스털링", "스타보이 찰리", "아리아 베넷"}
        at_start = {m.name for m in roster.active_at(0)}
        assert not (evolve & at_start), "Evolve가 0주차 명부에 섞였다"
        by_five = {m.name for m in roster.active_at(5 * WEEKS_PER_YEAR)}
        assert evolve <= by_five, "Evolve가 5년 안에 데뷔하지 않았다"
        # **위상 표(§3-D95)가 Evolve로 적은 사람들만 로우카드다.** 아론 루크는 원본
        # CSV에서 Evolve지만 사용자 표에서는 NXT 미드카드다 — 그 어긋남은 사용자에게
        # 보고했고, 데이터는 각자의 원본을 따른다(브랜드는 CSV · 위상은 표).
        listed_as_evolve = {"제나 스털링", "스타보이 찰리", "아리아 베넷"}
        assert all(
            m.start_tier is roster.RivalTier.LOW_CARD
            for m in roster.ROSTER
            if m.name in listed_as_evolve
        )

    def test_a_prospect_climbs_with_experience(self) -> None:
        rookie = next(
            m
            for m in roster.ROSTER
            if m.start_tier is roster.RivalTier.LOW_CARD and m.debut_week == 0
        )
        assert roster.tier_at(rookie, 0) is roster.RivalTier.LOW_CARD
        assert roster.tier_at(rookie, 12 * WEEKS_PER_YEAR) > roster.RivalTier.LOW_CARD

    def test_the_table_wins_on_day_one(self) -> None:
        """0주차 위상은 **사용자 표가 이긴다** (§3-D95).

        예외는 하나다 — 은퇴가 코앞인 사람은 한 칸 내려온 채로 시작한다(`DECLINE_BEFORE`).
        R-트루스처럼 오늘 쉰넷인 선수가 그렇다: 표의 미드카드로 시작하되 마지막 두 해는
        아래에서 후배를 올려 준다.
        """
        for member in roster.active_at(0):
            fading = (
                member.retire_week is not None
                and member.retire_week <= roster.DECLINE_BEFORE
            )
            if fading:
                assert roster.tier_at(member, 0) <= member.start_tier
            else:
                assert roster.tier_at(member, 0) is member.start_tier

    def test_every_pool_stays_stocked_for_thirty_years(self) -> None:
        for year in range(0, 31):
            for gender in Gender:
                for tier in roster.RivalTier:
                    pool = roster.pool_for(gender, tier, year * WEEKS_PER_YEAR)
                    assert len(pool) >= roster.MIN_POOL, (year, gender, tier)

    def test_a_rival_is_picked_from_that_weeks_roster(self) -> None:
        run = make_run(week=25 * WEEKS_PER_YEAR, stats=WrestlerStats(popularity=70))
        # **그 판의 이름으로 견준다** — 가상 선수 이름은 시드를 탄다 (§3-D59).
        active = {
            roster.name_at(m, run.week, run.seed) for m in roster.active_at(run.week)
        }
        for seed in range(20):
            name = rivalry_engine.pick_rival(run, SeededRoll(seed, 1, "riv"))
            assert name in active

    def test_an_existing_rival_is_not_picked_again(self) -> None:
        taken = roster.pool_for(Gender.MALE, roster.RivalTier.LOW_CARD)[0]
        run = make_run(rivalries=(rival(taken, 50),))
        for seed in range(30):
            assert rivalry_engine.pick_rival(run, SeededRoll(seed, 1, "riv")) != taken


# ── T5 덱 ────────────────────────────────────────────────────


class TestDeckLoads:
    def test_the_whole_deck_loads(self) -> None:
        assert len(DECK) >= 190
        assert sum(len(c.choices) for c in DECK) >= 420

    def test_codes_are_unique(self) -> None:
        assert len({c.code for c in DECK}) == len(DECK)

    def test_camel_case_becomes_snake_case(self) -> None:
        keys = {k for c in DECK for ch in c.choices for k, _ in ch.effects}
        assert "in_ring" in keys and "inRing" not in keys
        assert "mic_work" in keys and "micWork" not in keys

    def test_every_choice_moves_both_shown_stats(self) -> None:
        for card in DECK:
            for ch in card.choices:
                e = dict(ch.effects)
                assert "popularity" in e and "in_ring" in e
                assert e["popularity"] != e["in_ring"]

    def test_wear_is_not_a_clampable_stat(self) -> None:
        card = next(c for c in DECK for ch in c.choices if ch.wear_delta)
        ch = next(c2 for c2 in card.choices if c2.wear_delta)
        assert "wear" not in ch.stat_deltas()

    def test_in_ring_cards_are_the_bulk_of_the_deck(self) -> None:
        in_ring = sum(1 for c in DECK if c.arena is Arena.IN_RING)
        assert in_ring / len(DECK) >= 0.40

    def test_main_cards_are_all_once(self) -> None:
        assert all(c.once for c in DECK if c.kind is CardKind.MAIN)


class TestEligibility:
    def test_a_once_card_is_not_offered_twice(self) -> None:
        card = next(c for c in DECK if c.once)
        run = make_run(week=1500, stats=WrestlerStats(popularity=70, in_ring=70))
        assert not event_draw.is_eligible(
            run.evolve(seen_events=frozenset({card.code})), card
        )

    def test_region_cards_only_fire_for_that_region(self) -> None:
        card = BY_CODE["kr_homecoming_show"]
        korean = make_run(week=200)
        assert event_draw.is_eligible(korean, card)

    def test_style_cards_only_fire_for_that_style(self) -> None:
        card = BY_CODE["hf_body_toll"]
        flyer = make_run(week=200, style=PlayStyle.HIGH_FLYER)
        tech = make_run(week=200, style=PlayStyle.TECHNICIAN)
        assert event_draw.is_eligible(flyer, card)
        assert not event_draw.is_eligible(tech, card)

    def test_rivalry_cards_need_a_rivalry(self) -> None:
        card = BY_CODE["riv_backstage_ambush"]
        alone = make_run(week=300)
        feuding = alone.evolve(rivalries=(rival("숙적", 80),))
        assert not event_draw.is_eligible(alone, card)
        assert event_draw.is_eligible(feuding, card)

    def test_condition_cards_need_the_right_grade(self) -> None:
        card = BY_CODE["inj_rehab_grind"]
        healthy = make_run(week=300)
        hurt = healthy.evolve(condition=Condition().injured(InjuryGrade.SERIOUS, 12))
        assert not event_draw.is_eligible(healthy, card)
        assert event_draw.is_eligible(hurt, card)

    def test_brand_gated_cards_stay_on_their_own_stage(self) -> None:
        card = BY_CODE["callup_injury_replacement"]
        base = make_run(week=40, stats=WrestlerStats(popularity=40))
        assert event_draw.is_eligible(base.evolve(brand=Brand.NXT), card)
        assert not event_draw.is_eligible(base.evolve(brand=Brand.RAW), card)

    def test_only_the_accepting_choice_carries_the_call_up_flag(self) -> None:
        # 거절 선택지가 플래그를 달면 안 부른 커리어가 조용히 올라간다.
        for code in ("callup_injury_replacement", "callup_live_hole"):
            card = BY_CODE[code]
            carriers = [
                c for c in card.choices if championship.EMERGENCY_CALLUP_FLAG in c.flags
            ]
            assert len(carriers) == 1

    def test_flag_gated_cards_need_the_flag(self) -> None:
        card = BY_CODE["ring_cash_in_moment"]
        plain = make_run(week=300, stats=WrestlerStats(popularity=40))
        holder = plain.evolve(flags=frozenset({"contract_in_hand"}))
        assert not event_draw.is_eligible(plain, card)
        assert event_draw.is_eligible(holder, card)


class TestRepetitionCeiling:
    """§11-19 — `weekly` 한 판에서 같은 카드가 5회를 넘지 않는다.

    **한 시점의 후보 수가 아니라 30년을 돌려서 센다.** 예전에는 권역×스타일 조합을
    전수로 훑어 "카드당 3.7회"를 얻었는데, 그건 한 판이 실제로 겪는 분포가 아니다 —
    진짜 커리어를 돌리자 최대 7회가 나왔다(2026-08-07).
    """

    MAX_CARD_REPEAT = 5

    def test_no_card_repeats_too_often_in_one_career(self) -> None:
        from collections import Counter

        from wwe_game.domain.constants.countries import Country
        from wwe_game.domain.entities.career_run import start_run
        from wwe_game.domain.services import career_end
        from wwe_game.domain.services.week_simulation import apply_week, simulate_week
        from wwe_game.domain.value_objects.game_mode import game_mode_of
        from wwe_game.domain.value_objects.wrestler_identity import (
            RingName,
            WrestlerIdentity,
        )

        # 스타일이 21종이라 권역 다섯을 돌려 쓴다. 조합을 전수로 훑는 게 목적이 아니라
        # **한 판이 겪는 분포**를 재는 자리이므로(§3-D15-1) 짝은 고정이기만 하면 된다.
        countries = [Country.KR, Country.US, Country.JP, Country.MX, Country.GB]
        worst = 0
        for index, style in enumerate(PlayStyle):
            country = countries[index % len(countries)]
            identity = WrestlerIdentity(
                name=RingName("장상호"),
                gender=Gender.MALE,
                country=country,
                play_style=style,
            )
            run = start_run(
                identity=identity,
                mode=game_mode_of("weekly"),
                seed=1100 + index,
                user_id=1,
            )
            drawn: Counter[str] = Counter()
            while run.is_active and run.week < 1560:
                if run.is_blocked:
                    code = run.pending_event.code
                    drawn[code] += 1
                    run = event_draw.resolve_choice(run, BY_CODE[code].choices[0].code)
                    run = career_end.close_if_ended(run)
                    continue
                run = apply_week(run, simulate_week(run))
                run = career_end.track_decline(career_end.track_release(run))
                run = career_end.close_if_ended(run)
            if drawn:
                worst = max(worst, drawn.most_common(1)[0][1])
        assert worst <= self.MAX_CARD_REPEAT, f"같은 카드가 {worst}회 나왔다"

    def test_the_cooldown_fits_inside_the_memory(self) -> None:
        # 쿨다운이 기억보다 길면 뒤쪽이 그냥 버려진다 — 나눗수를 올려도 반복이 안 준다.
        from wwe_game.domain.constants.event_deck import DECK

        assert event_draw._cooldown(len(DECK)) <= event_draw.RECENT_MEMORY


class TestDraw:
    def test_the_same_seed_draws_the_same_event(self) -> None:
        run = make_run(week=200, stats=WrestlerStats(popularity=45, in_ring=45))
        assert event_draw.draw_event(run) == event_draw.draw_event(run)

    def test_budget_runs_out(self) -> None:
        run = make_run(week=200)
        spent = run.evolve(events_fired=run.mode.event_budget)
        assert event_draw.event_chance(spent) == 0.0
        assert event_draw.draw_event(spent) is None

    def test_chance_stays_alive_late_in_the_career(self) -> None:
        # 초반에 몰아 쓰고 후반이 조용해지면 안 된다.
        early = make_run(week=100).evolve(events_fired=20)
        late = make_run(week=1400).evolve(events_fired=280)
        assert event_draw.event_chance(late) > event_draw.event_chance(early)

    def test_cooldown_keeps_a_card_from_repeating_immediately(self) -> None:
        base = make_run(stats=WrestlerStats(popularity=45, in_ring=45))
        run, drawn = next(
            (r, d)
            for w in range(200, 400)
            if (d := event_draw.draw_event(r := base.evolve(week=w))) is not None
        )
        blocked = run.evolve(recent_events=(drawn.code,) * 20)
        again = event_draw.draw_event(blocked)
        assert again is None or again.code != drawn.code


class TestResolveChoice:
    def test_a_choice_moves_stats_and_records_the_card(self) -> None:
        card = BY_CODE["ir_tape_study"]
        run = make_run(week=300).evolve(
            pending_event=event_draw.EventInstance(code=card.code, week=300)
        )
        after = event_draw.resolve_choice(run, "study_all_night")
        assert after.pending_event is None
        assert after.events_fired == 1
        assert after.stats.in_ring > run.stats.in_ring

    def test_flags_are_recorded(self) -> None:
        card = BY_CODE["bs_leak_to_the_dirtsheet"]
        run = make_run(week=300).evolve(
            pending_event=event_draw.EventInstance(code=card.code, week=300)
        )
        assert "suspension_pending" in event_draw.resolve_choice(run, "leak").flags

    def test_a_once_card_is_remembered(self) -> None:
        card = next(c for c in DECK if c.once)
        run = make_run(week=1400, stats=WrestlerStats(popularity=70)).evolve(
            pending_event=event_draw.EventInstance(code=card.code, week=1400)
        )
        after = event_draw.resolve_choice(run, card.choices[0].code)
        assert card.code in after.seen_events

    def test_an_unknown_choice_is_rejected(self) -> None:
        run = make_run(week=300).evolve(
            pending_event=event_draw.EventInstance(code="ir_tape_study", week=300)
        )
        with pytest.raises(ValueError, match="선택할 수 없는"):
            event_draw.resolve_choice(run, "nope")

    def test_answering_without_a_pending_event_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="대기 중인 이벤트가 없습니다"):
            event_draw.resolve_choice(make_run(), "whatever")

    def test_a_career_ending_choice_is_a_gamble_not_a_certainty(self) -> None:
        # 확정 종료로 두면 그 카드를 만난 커리어의 대부분이 거기서 끝난다.
        card = BY_CODE["act4_body_gives_out"]
        choice = card.choice("finish_the_match")
        assert choice is not None and choice.career_ending
        assert choice.injury_risk < 0.5

        outcomes = set()
        for seed in range(40):
            run = make_run(
                seed=seed,
                week=1300,
                stats=WrestlerStats(popularity=70),
                condition=Condition(wear=60),
            ).evolve(pending_event=event_draw.EventInstance(code=card.code, week=1300))
            outcomes.add(
                event_draw.resolve_choice(run, "finish_the_match").condition.grade
            )
        assert InjuryGrade.CAREER_ENDING in outcomes
        assert InjuryGrade.SERIOUS in outcomes


class TestNobodyFightsThemselves:
    def test_the_player_is_not_drawn_as_a_rival(self) -> None:
        """실존 선수를 골라 **그 선수가 되는** 시스템이라(§3-D10-1 개정) 플레이어
        이름이 명부에 그대로 있을 수 있다. 자기 자신과 대립하면 안 된다."""
        from _helpers import make_run
        from wwe_game.domain.constants import roster
        from wwe_game.domain.services.rivalry_engine import pick_rival
        from wwe_game.domain.services.seeded_roll import RIVALRY, SeededRoll
        from wwe_game.domain.value_objects.wrestler_identity import RingName
        from wwe_game.domain.value_objects.wrestler_stats import WrestlerStats

        base = make_run(seed=1, stats=WrestlerStats(popularity=70))
        mine = roster.pool_for(base.identity.gender, roster.RivalTier.UPPER_CARD, 0)[0]
        run = base.evolve(
            identity=base.identity.__class__(
                name=RingName(mine),
                gender=base.identity.gender,
                country=base.identity.country,
                play_style=base.identity.play_style,
            )
        )
        drawn = {pick_rival(run, SeededRoll(seed, 1, RIVALRY)) for seed in range(200)}
        assert mine not in drawn, "플레이어가 자기 자신을 라이벌로 만났다"
