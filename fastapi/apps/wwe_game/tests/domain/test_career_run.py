"""T2 애그리거트 — 불변식 · 액트 파생 · 종료 전이."""

from __future__ import annotations

import dataclasses

import pytest
from wwe_game.domain.constants.career_clock import CAREER_WEEKS
from wwe_game.domain.constants.countries import Country
from wwe_game.domain.entities.career_run import (
    CareerRun,
    EndReason,
    EventInstance,
    Rivalry,
    RivalryStage,
    RunStatus,
    start_run,
)
from wwe_game.domain.exceptions import InvalidCareerRunError, RunNotActiveError
from wwe_game.domain.value_objects.game_mode import game_mode_of
from wwe_game.domain.value_objects.wrestler_identity import (
    Gender,
    PlayStyle,
    RingName,
    WrestlerIdentity,
)
from wwe_game.domain.value_objects.wrestler_stats import WrestlerStats


@pytest.fixture
def identity() -> WrestlerIdentity:
    return WrestlerIdentity(
        name=RingName("장상호"),
        gender=Gender.MALE,
        country=Country.KR,
        play_style=PlayStyle.HIGH_FLYER,
    )


@pytest.fixture
def run(identity: WrestlerIdentity) -> CareerRun:
    return start_run(identity=identity, mode=game_mode_of("weekly"), seed=42, user_id=7)


class TestStart:
    def test_new_career_begins_at_twenty_week_zero(self, run: CareerRun) -> None:
        assert run.week == 0
        assert run.age == 20
        assert run.status is RunStatus.ACTIVE
        assert run.end_reason is None
        assert not run.is_blocked

    def test_guest_run_has_no_user_id(self, identity: WrestlerIdentity) -> None:
        guest = start_run(identity=identity, mode=game_mode_of("yearly"), seed=1)
        assert guest.user_id is None

    def test_run_is_immutable(self, run: CareerRun) -> None:
        with pytest.raises(dataclasses.FrozenInstanceError):
            run.week = 10  # type: ignore[misc]


class TestInvariants:
    def test_week_cannot_exceed_the_career_length(self, run: CareerRun) -> None:
        assert run.evolve(week=CAREER_WEEKS).week == CAREER_WEEKS
        with pytest.raises(InvalidCareerRunError):
            run.evolve(week=CAREER_WEEKS + 1)
        with pytest.raises(InvalidCareerRunError):
            run.evolve(week=-1)

    def test_ended_run_must_carry_a_reason(self, run: CareerRun) -> None:
        with pytest.raises(InvalidCareerRunError):
            run.evolve(status=RunStatus.RETIRED)

    def test_active_run_must_not_carry_a_reason(self, run: CareerRun) -> None:
        with pytest.raises(InvalidCareerRunError):
            run.evolve(end_reason=EndReason.PLAYER)

    def test_completed_is_reachable_only_by_full_term(self, run: CareerRun) -> None:
        with pytest.raises(InvalidCareerRunError):
            run.evolve(status=RunStatus.COMPLETED, end_reason=EndReason.INJURY)

    def test_ended_run_cannot_hold_a_pending_event(self, run: CareerRun) -> None:
        with pytest.raises(InvalidCareerRunError):
            run.evolve(
                status=RunStatus.RETIRED,
                end_reason=EndReason.PLAYER,
                pending_event=EventInstance(code="x", week=1),
            )

    def test_heat_bounds(self) -> None:
        with pytest.raises(InvalidCareerRunError):
            Rivalry(
                rival_name="상대", stage=RivalryStage.HEATED, heat=101, started_week=0
            )


class TestAct:
    @pytest.mark.parametrize(
        ("week", "popularity", "expected"),
        [
            (0, 0, 1),
            (0, 29, 1),
            (0, 30, 2),
            (0, 59, 2),
            (0, 60, 3),
            (0, 100, 3),
            # 인기도가 나이보다 우선한다 — 인기 없는 노장만 43세에 황혼으로 간다
            (23 * 52, 0, 4),  # 43세 · 인기도 0 → 황혼
            (23 * 52, 100, 3),  # 43세 · 인기도 100 → 아직 메인이벤터
            (26 * 52, 100, 3),  # 46세 · 인기도 100 → 아직 버틴다
            (27 * 52, 100, 4),  # 47세 → 인기도가 높아도 황혼
            (22 * 52, 0, 1),  # 42세 · 인기도 0 → 나이만으로는 액트가 안 오른다
        ],
    )
    def test_act_is_derived_from_popularity_and_age(
        self, run: CareerRun, week: int, popularity: int, expected: int
    ) -> None:
        assert (
            run.evolve(week=week, stats=WrestlerStats(popularity=popularity)).act
            == expected
        )

    def test_act_can_go_back_down(self, run: CareerRun) -> None:
        # 한 방향으로만 흐르면 모든 판이 같은 모양이 된다 (하네스 §5).
        risen = run.evolve(stats=WrestlerStats(popularity=70))
        assert risen.act == 3
        assert risen.evolve(stats=WrestlerStats(popularity=35)).act == 2


class TestDerived:
    def test_pending_event_blocks_progress(self, run: CareerRun) -> None:
        blocked = run.evolve(
            pending_event=EventInstance(code="act1_debut_night", week=3)
        )
        assert blocked.is_blocked

    def test_weeks_remaining(self, run: CareerRun) -> None:
        assert run.weeks_remaining == CAREER_WEEKS
        assert run.evolve(week=60).weeks_remaining == CAREER_WEEKS - 60

    def test_ticks_elapsed_differs_per_mode(self, identity: WrestlerIdentity) -> None:
        for code, expected in [
            ("weekly", 104),
            ("monthly", 26),
            ("quarterly", 8),
            ("yearly", 2),
        ]:
            r = start_run(identity=identity, mode=game_mode_of(code), seed=1).evolve(
                week=104
            )
            assert r.ticks_elapsed == expected

    def test_retirement_age_reached(self, run: CareerRun) -> None:
        assert not run.is_at_retirement_age
        assert run.evolve(week=CAREER_WEEKS).is_at_retirement_age


class TestEnding:
    def test_full_term_is_completed(self, run: CareerRun) -> None:
        ended = run.evolve(week=CAREER_WEEKS).ended(EndReason.AGE_50)
        assert ended.status is RunStatus.COMPLETED

    @pytest.mark.parametrize(
        "reason", [EndReason.PLAYER, EndReason.DECLINE, EndReason.INJURY]
    )
    def test_early_ending_is_retired(self, run: CareerRun, reason: EndReason) -> None:
        ended = run.ended(reason)
        assert ended.status is RunStatus.RETIRED
        assert ended.end_reason is reason

    def test_ending_clears_the_pending_event(self, run: CareerRun) -> None:
        blocked = run.evolve(pending_event=EventInstance(code="x", week=1))
        assert blocked.ended(EndReason.INJURY).pending_event is None

    def test_an_ended_run_cannot_end_again(self, run: CareerRun) -> None:
        ended = run.ended(EndReason.PLAYER)
        with pytest.raises(RunNotActiveError):
            ended.ended(EndReason.DECLINE)

    def test_require_active_guards_ended_runs(self, run: CareerRun) -> None:
        run.require_active()  # 진행 중이면 통과
        with pytest.raises(RunNotActiveError):
            run.ended(EndReason.PLAYER).require_active()
