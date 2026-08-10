"""T3 은퇴 — 4조건이 각각 실제로 발생한다 (하네스 §11-21)."""

from __future__ import annotations

from _helpers import make_run  # noqa: I001  (tests 트리에 __init__.py가 없다)
from wwe_game.domain.constants import career_rules as rules
from wwe_game.domain.constants.career_clock import CAREER_WEEKS
from wwe_game.domain.entities.career_run import EndReason, RunStatus
from wwe_game.domain.services.career_end import (
    check_end,
    close_if_ended,
    is_at_release_risk,
    is_declining,
    release_grace_weeks,
    standing_of,
    track_decline,
    track_release,
)
from wwe_game.domain.value_objects.condition import Condition, InjuryGrade
from wwe_game.domain.value_objects.wrestler_stats import WrestlerStats


class TestFullTerm:
    def test_reaching_1560_weeks_completes_the_career(self) -> None:
        run = make_run(week=CAREER_WEEKS)
        assert check_end(run) is EndReason.AGE_50
        assert close_if_ended(run).status is RunStatus.COMPLETED

    def test_full_term_outranks_injury_and_decline(self) -> None:
        run = make_run(
            week=CAREER_WEEKS,
            condition=Condition().injured(InjuryGrade.CAREER_ENDING, 1),
        ).evolve(decline_weeks=999)
        assert check_end(run) is EndReason.AGE_50


class TestInjuryEnding:
    def test_career_ending_injury_closes_the_run(self) -> None:
        run = make_run(condition=Condition().injured(InjuryGrade.CAREER_ENDING, 1))
        assert check_end(run) is EndReason.INJURY
        closed = close_if_ended(run)
        assert closed.status is RunStatus.RETIRED
        assert closed.end_reason is EndReason.INJURY

    def test_a_minor_injury_does_not_end_anything(self) -> None:
        run = make_run(condition=Condition().injured(InjuryGrade.MINOR, 4))
        assert check_end(run) is None


class TestDecline:
    def test_popularity_outweighs_skill_in_standing(self) -> None:
        popular = make_run(stats=WrestlerStats(popularity=40, in_ring=10))
        skilled = make_run(stats=WrestlerStats(popularity=10, in_ring=40))
        assert standing_of(popular) > standing_of(skilled)

    def test_a_popular_veteran_is_never_pushed_out(self) -> None:
        run = make_run(week=20 * 52, stats=WrestlerStats(popularity=60, in_ring=20))
        assert run.age >= rules.DECLINE_CHECK_AGE
        assert not is_declining(run)

    def test_at_equal_stat_budget_popularity_saves_and_skill_does_not(self) -> None:
        # 같은 총량 50점을 어디에 넣었는지가 자리를 가른다 — 인기도 우선의 실제 의미.
        popular = make_run(week=20 * 52, stats=WrestlerStats(popularity=40, in_ring=10))
        skilled = make_run(week=20 * 52, stats=WrestlerStats(popularity=10, in_ring=40))
        assert not is_declining(popular)
        assert is_declining(skilled)

    def test_a_forgotten_wrestler_declines(self) -> None:
        run = make_run(week=20 * 52, stats=WrestlerStats(popularity=5, in_ring=40))
        assert is_declining(run)

    def test_an_exceptional_worker_keeps_their_spot(self) -> None:
        # 아무도 안 찾아도 경기력이 아주 높으면 자리는 남는다. 인기도가 3배 무게일 뿐
        # 경기력을 무시하는 것은 아니다.
        run = make_run(week=20 * 52, stats=WrestlerStats(popularity=5, in_ring=80))
        assert not is_declining(run)

    def test_under_thirty_five_is_never_declining(self) -> None:
        run = make_run(week=10 * 52, stats=WrestlerStats(popularity=0, in_ring=0))
        assert run.age < rules.DECLINE_CHECK_AGE
        assert not is_declining(run)

    def test_wear_drags_standing_down(self) -> None:
        stats = WrestlerStats(popularity=30, in_ring=30)
        fresh = make_run(stats=stats, condition=Condition(wear=0))
        worn = make_run(stats=stats, condition=Condition(wear=80))
        assert standing_of(worn) < standing_of(fresh)

    def test_decline_needs_the_full_grace_period(self) -> None:
        run = make_run(week=20 * 52, stats=WrestlerStats(popularity=5, in_ring=5))
        for _ in range(rules.DECLINE_GRACE_WEEKS - 1):
            run = track_decline(run)
            assert check_end(run) is None
        run = track_decline(run)
        assert check_end(run) is EndReason.DECLINE

    def test_recovering_standing_resets_the_counter(self) -> None:
        run = make_run(week=20 * 52, stats=WrestlerStats(popularity=5, in_ring=5))
        for _ in range(10):
            run = track_decline(run)
        assert run.decline_weeks == 10
        recovered = track_decline(run.evolve(stats=WrestlerStats(popularity=70)))
        assert recovered.decline_weeks == 0


class TestPlayerEnding:
    def test_player_can_close_at_any_time(self) -> None:
        run = make_run(week=300)
        assert check_end(run) is None  # 자동 조건은 하나도 안 걸린다
        closed = run.ended(EndReason.PLAYER)
        assert closed.status is RunStatus.RETIRED
        assert closed.end_reason is EndReason.PLAYER


class TestAllFourReasonsAreReachable:
    def test_each_reason_has_a_producing_path(self) -> None:
        reached = {
            EndReason.AGE_50: check_end(make_run(week=CAREER_WEEKS)),
            EndReason.INJURY: check_end(
                make_run(condition=Condition().injured(InjuryGrade.CAREER_ENDING, 1))
            ),
            EndReason.DECLINE: check_end(
                make_run(
                    week=20 * 52, stats=WrestlerStats(popularity=0, in_ring=0)
                ).evolve(decline_weeks=rules.DECLINE_GRACE_WEEKS)
            ),
            EndReason.PLAYER: make_run().ended(EndReason.PLAYER).end_reason,
        }
        assert all(actual is expected for expected, actual in reached.items())

    def test_an_already_closed_run_reports_no_new_reason(self) -> None:
        assert check_end(make_run().ended(EndReason.PLAYER)) is None


class TestRelease:
    """방출 — 부진과 다른 실패다. 읽는 스탯도 다르다."""

    def test_a_wrecked_reputation_puts_you_at_risk(self) -> None:
        run = make_run(
            stats=WrestlerStats(
                backstage=rules.RELEASE_BACKSTAGE_FLOOR - 1, popularity=20
            )
        )
        assert is_at_release_risk(run)

    def test_a_solid_reputation_is_safe(self) -> None:
        run = make_run(stats=WrestlerStats(backstage=50, popularity=20))
        assert not is_at_release_risk(run)

    def test_a_star_is_tolerated_no_matter_the_reputation(self) -> None:
        # 돈이 되면 참아준다 — 인기도 우선이라는 대전제가 여기에도 걸린다.
        run = make_run(
            stats=WrestlerStats(backstage=0, popularity=rules.RELEASE_POPULARITY_SHIELD)
        )
        assert not is_at_release_risk(run)

    def test_release_has_no_age_gate_unlike_decline(self) -> None:
        # 부진은 35세부터지만 방출은 신인에게도 온다.
        rookie = make_run(week=52, stats=WrestlerStats(backstage=5, popularity=10))
        assert rookie.age < rules.DECLINE_CHECK_AGE
        assert not is_declining(rookie)
        assert is_at_release_risk(rookie)

    def test_release_needs_the_grace_period(self) -> None:
        run = make_run(stats=WrestlerStats(backstage=5, popularity=10))
        for _ in range(rules.RELEASE_GRACE_WEEKS - 1):
            run = track_release(run)
            assert check_end(run) is None
        assert check_end(track_release(run)) is EndReason.RELEASED

    def test_recovering_reputation_resets_the_counter(self) -> None:
        run = make_run(stats=WrestlerStats(backstage=5, popularity=10))
        for _ in range(6):
            run = track_release(run)
        assert run.release_weeks == 6
        assert (
            track_release(run.evolve(stats=WrestlerStats(backstage=60))).release_weeks
            == 0
        )

    def test_a_prior_suspension_halves_the_patience(self) -> None:
        clean = make_run(stats=WrestlerStats(backstage=5, popularity=10))
        marked = clean.evolve(flags=frozenset({"suspension_pending"}))
        assert release_grace_weeks(marked) < release_grace_weeks(clean)

    def test_release_closes_the_run_as_retired(self) -> None:
        run = make_run(stats=WrestlerStats(backstage=5, popularity=10)).evolve(
            release_weeks=rules.RELEASE_GRACE_WEEKS
        )
        closed = close_if_ended(run)
        assert closed.status is RunStatus.RETIRED
        assert closed.end_reason is EndReason.RELEASED

    def test_release_outranks_decline(self) -> None:
        # 잘린 선수는 밀려날 기회조차 없다.
        run = make_run(
            week=20 * 52, stats=WrestlerStats(backstage=5, popularity=5, in_ring=5)
        ).evolve(
            release_weeks=rules.RELEASE_GRACE_WEEKS,
            decline_weeks=rules.DECLINE_GRACE_WEEKS,
        )
        assert check_end(run) is EndReason.RELEASED

    def test_full_term_still_outranks_release(self) -> None:
        run = make_run(
            week=CAREER_WEEKS, stats=WrestlerStats(backstage=0, popularity=0)
        ).evolve(release_weeks=999)
        assert check_end(run) is EndReason.AGE_50

    def test_all_five_endings_are_reachable(self) -> None:
        assert {
            check_end(make_run(week=CAREER_WEEKS)),
            check_end(
                make_run(condition=Condition().injured(InjuryGrade.CAREER_ENDING, 1))
            ),
            check_end(
                make_run(
                    week=20 * 52, stats=WrestlerStats(popularity=0, in_ring=0)
                ).evolve(decline_weeks=rules.DECLINE_GRACE_WEEKS)
            ),
            check_end(
                make_run(stats=WrestlerStats(backstage=0, popularity=0)).evolve(
                    release_weeks=rules.RELEASE_GRACE_WEEKS
                )
            ),
            make_run().ended(EndReason.PLAYER).end_reason,
        } == {
            EndReason.AGE_50,
            EndReason.INJURY,
            EndReason.DECLINE,
            EndReason.RELEASED,
            EndReason.PLAYER,
        }


class TestRookiesAreNotReleased:
    """육성 브랜드에 있는 동안은 자르지 않는다 (2026-08-10 사용자 결정 · §3-D24)."""

    def test_nxt_is_immune(self) -> None:
        from _helpers import make_run
        from wwe_game.domain.services.career_end import is_at_release_risk
        from wwe_game.domain.value_objects.title import Brand
        from wwe_game.domain.value_objects.wrestler_stats import WrestlerStats

        broke = WrestlerStats(popularity=10, backstage=0)
        assert not is_at_release_risk(make_run(brand=Brand.NXT).evolve(stats=broke))
        assert is_at_release_risk(make_run(brand=Brand.RAW).evolve(stats=broke))

    def test_the_grace_is_half_a_year(self) -> None:
        from wwe_game.domain.constants import career_rules as rules

        # 12주는 회복할 틈이 없어 1년차 신인이 즉사했다 (실측 0.8년).
        assert rules.RELEASE_GRACE_WEEKS == 26
