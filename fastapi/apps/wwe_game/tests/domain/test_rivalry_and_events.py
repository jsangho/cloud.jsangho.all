"""T4 대립 엔진 + T5 덱 로더·추첨."""

from __future__ import annotations

import pytest
from _helpers import make_run  # noqa: I001
from wwe_game.domain.constants import roster
from wwe_game.domain.constants.event_deck import BY_CODE, DECK, Arena, CardKind
from wwe_game.domain.entities.career_run import Rivalry, RivalryStage
from wwe_game.domain.services import event_draw, rivalry_engine
from wwe_game.domain.services.seeded_roll import SeededRoll
from wwe_game.domain.value_objects.condition import Condition, InjuryGrade
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
        assert roster.tier_for_popularity(10) is roster.RivalTier.PROSPECT
        assert roster.tier_for_popularity(40) is roster.RivalTier.MIDCARD
        assert roster.tier_for_popularity(80) is roster.RivalTier.MAIN_EVENT

    def test_a_woman_never_feuds_with_a_man(self) -> None:
        run = make_run(gender=Gender.FEMALE, stats=WrestlerStats(popularity=70))
        womens = {m.name for m in roster.ROSTER if m.gender is Gender.FEMALE}
        for seed in range(30):
            name = rivalry_engine.pick_rival(run, SeededRoll(seed, 1, "riv"))
            assert name in womens

    def test_an_existing_rival_is_not_picked_again(self) -> None:
        taken = roster.pool_for(Gender.MALE, roster.RivalTier.PROSPECT)[0]
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

    def test_flag_gated_cards_need_the_flag(self) -> None:
        card = BY_CODE["ring_cash_in_moment"]
        plain = make_run(week=300, stats=WrestlerStats(popularity=40))
        holder = plain.evolve(flags=frozenset({"contract_in_hand"}))
        assert not event_draw.is_eligible(plain, card)
        assert event_draw.is_eligible(holder, card)


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
