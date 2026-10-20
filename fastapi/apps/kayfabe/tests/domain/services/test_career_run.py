"""가상 선수 키우기 엔진 (`domain/services/career_run`).

**붙드는 것은 재미가 아니라 계약이다.**

1. **끝은 은퇴뿐** — 월챔을 들어도 런이 끝나지 않는다(2026-10-20 사용자 결정).
2. **결정론** — 같은 상태·같은 선택이면 같은 결과. 다시 보내 주사위를 굴릴 수 없다.
3. **방어는 재위를 늘리지 않는다** — 지킨 것은 새 재위가 아니다.
4. **인기도 바닥이 10** — 0이면 승률이 굳어 나선에서 못 빠져나온다(첫 시험 런이
   거기 갇혔다).
5. **사다리와 브랜드 게이트** — NXT 벨트는 NXT 에서만, 나머지는 메인에서만.

순수 함수라 DB가 필요 없다.
"""

from __future__ import annotations

import pytest

from kayfabe.domain.services.career_run import (
    BELT_LADDER,
    MAX_POPULARITY,
    MAX_WEEKS,
    MIN_POPULARITY,
    CareerState,
    advance,
    is_defense,
    next_belt,
    win_chance,
)

_WORLD = "World Heavyweight Championship"
_NXT = "NXT Championship"
_IC = "Intercontinental Championship"


def _play(state: CareerState, limit: int = MAX_WEEKS + 5) -> CareerState:
    """자동으로 끝까지 돌린다 — 벨트가 열리면 도전, 아니면 경기."""
    for _ in range(limit):
        if state.outcome is not None:
            return state
        belt = next_belt(state)
        state = advance(state, choice="도전" if belt else "경기").state
    return state


class TestEndsOnlyInRetirement:
    def test_world_title_does_not_end_the_run(self) -> None:
        """**사용자 결정**: 월챔은 중간 목표다."""
        champ = CareerState(
            name="Ho", style="파워", brand="Raw", popularity=90, reigns=(_NXT, _IC)
        )
        result = advance(champ, choice="도전")
        assert result.report.belt == _WORLD
        if result.report.won:
            assert _WORLD in result.state.reigns
        assert result.state.outcome is None

    def test_the_run_ends_retired(self) -> None:
        assert _play(CareerState(name="Ho", style="파워")).outcome == "retired"

    def test_reigns_can_exceed_one(self) -> None:
        """월챔 뒤에도 주차가 비지 않는다 — 방어와 재도전이 있다."""
        final = _play(CareerState(name="Jay", style="하이플라이어"))
        assert len(final.reigns) >= 2

    def test_finished_run_is_returned_untouched(self) -> None:
        done = CareerState(name="Ho", style="파워", outcome="retired", week=41)
        assert advance(done, choice="경기").state == done


class TestDeterminism:
    def test_same_state_same_result(self) -> None:
        state = CareerState(name="Ho", style="테크니션", popularity=50)
        assert advance(state, choice="경기") == advance(state, choice="경기")

    def test_resending_cannot_reroll(self) -> None:
        """뽑기가 **상태에서 파생**되므로 다시 보내도 같은 승패다."""
        state = CareerState(name="Ho", style="파워", popularity=30)
        first = advance(state, choice="경기").report.won
        for _ in range(5):
            assert advance(state, choice="경기").report.won == first

    def test_input_state_is_not_mutated(self) -> None:
        state = CareerState(name="Ho", style="파워", popularity=30)
        advance(state, choice="경기")
        assert state.popularity == 30
        assert state.week == 1


class TestTitles:
    def test_defense_does_not_add_a_reign(self) -> None:
        champ = CareerState(
            name="Ho",
            style="파워",
            brand="Raw",
            popularity=MAX_POPULARITY,
            reigns=(_NXT, _IC, _WORLD),
            held=_WORLD,
        )
        assert is_defense(champ) is True
        result = advance(champ, choice="도전")
        assert result.report.kind == "방어전"
        assert len(result.state.reigns) == len(champ.reigns)

    def test_losing_a_defense_drops_the_belt(self) -> None:
        champ = CareerState(
            name="Loser",
            style="하이플라이어",
            brand="Raw",
            popularity=MIN_POPULARITY,
            reigns=(_WORLD,),
            held=_WORLD,
        )
        result = advance(champ, choice="도전")
        if result.report.won is False:
            assert result.state.held is None
            assert _WORLD in result.state.reigns

    def test_ladder_is_climbed_in_order(self) -> None:
        rookie = CareerState(name="Ho", style="파워", popularity=90)
        assert next_belt(rookie) == BELT_LADDER[0]

    def test_nxt_belt_is_closed_on_the_main_roster(self) -> None:
        moved = CareerState(name="Ho", style="파워", brand="Raw", popularity=90)
        assert next_belt(moved) == _IC

    def test_main_belts_are_closed_in_nxt(self) -> None:
        stuck = CareerState(
            name="Ho", style="파워", brand="NXT", popularity=90, reigns=(_NXT,)
        )
        assert next_belt(stuck) is None

    def test_world_can_be_challenged_again(self) -> None:
        """사다리 끝에서 도전할 것이 없어지면 남은 주차가 빈다."""
        veteran = CareerState(
            name="Ho",
            style="파워",
            brand="Raw",
            popularity=90,
            reigns=(_NXT, _IC, _WORLD),
        )
        assert next_belt(veteran) == _WORLD


class TestBounds:
    def test_popularity_floor_is_ten(self) -> None:
        low = CareerState(name="Ho", style="파워", popularity=MIN_POPULARITY)
        for _ in range(5):
            low = advance(low, choice="경기").state
        assert low.popularity >= MIN_POPULARITY

    def test_win_chance_keeps_upsets_possible(self) -> None:
        best = CareerState(name="Ho", style="파워", popularity=MAX_POPULARITY)
        assert win_chance(best, title_match=False) <= 0.85

    def test_injured_weeks_skip_matches(self) -> None:
        hurt = CareerState(name="Ho", style="파워", out_weeks=2, popularity=50)
        result = advance(hurt, choice="경기")
        assert result.report.kind == "결장"
        assert result.report.won is None
        assert result.state.out_weeks == 1
        assert result.state.wins == 0

    @pytest.mark.parametrize("style", ["파워", "테크니션", "하이플라이어"])
    def test_every_style_can_reach_the_world_title(self, style: str) -> None:
        """순수 열등인 스타일이 없어야 한다 — 하이플라이어가 그랬다가 고쳤다."""
        champ = CareerState(
            name="Jay", style=style, brand="Raw", popularity=90, reigns=(_NXT, _IC)
        )
        assert next_belt(champ) == _WORLD
