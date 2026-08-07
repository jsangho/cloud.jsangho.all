"""선택이 남긴 표식이 실제로 읽히는가 (하네스 §3-D26).

**이 파일이 존재하는 이유**: 2026-08-07 감사에서 플래그 30종 중 **21종이 아무도 안 읽는
값**이었다. 그중 `painkiller_habit`은 `CareerRun.flags` 설명이 "부상 굴림을 올린다"고
약속까지 해 둔 것이었다 — 문서만 있고 코드가 없었다.

표식은 조용히 죽는다. 카드를 추가할 때 `flags`에 새 이름을 적어도 아무 일이 안 일어나고,
그걸 알려 주는 건 아무것도 없다. 그래서 **덱과 규칙을 대조하는 검사**를 여기 둔다.
"""

from __future__ import annotations

import pytest
from _helpers import make_run  # noqa: I001  (tests 트리에 __init__.py가 없다)
from wwe_game.domain.constants import career_rules as rules
from wwe_game.domain.constants.career_flags import (
    GROUNDED,
    GRUDGE,
    MANAGER,
    NEMESIS_LOCKED,
    PAINKILLER,
    PUSH_FROZEN,
    RULE_READ_FLAGS,
)
from wwe_game.domain.constants.event_deck import DECK
from wwe_game.domain.entities.career_run import Rivalry, RivalryStage
from wwe_game.domain.services import rivalry_engine
from wwe_game.domain.services.seeded_roll import SeededRoll
from wwe_game.domain.services.week_simulation import injury_chance
from wwe_game.domain.value_objects.week_report import WeekKind

DECK_FLAGS = {flag for card in DECK for ch in card.choices for flag in ch.flags}
CARD_READ_FLAGS = {flag for card in DECK for flag in card.requires.flags}


class TestTheDeckAndRulesAgree:
    @pytest.mark.parametrize("flag", sorted(RULE_READ_FLAGS))
    def test_every_rule_flag_is_actually_set_somewhere(self, flag: str) -> None:
        # 규칙만 있고 그 표식을 남기는 선택지가 없으면 영영 발동하지 않는다.
        assert flag in DECK_FLAGS, f"{flag}을 남기는 선택지가 덱에 없다"

    def test_the_rule_flags_are_not_also_card_conditions(self) -> None:
        # 겹쳐도 동작은 하지만, 한 표식이 두 방식으로 읽히면 균형을 재기 어려워진다.
        assert not (RULE_READ_FLAGS & CARD_READ_FLAGS)

    def test_the_dead_flag_count_does_not_grow(self) -> None:
        """아직 아무도 안 읽는 표식이 **늘지 않는지** 지킨다.

        지금 남은 것은 콘텐츠 부채다 — 콜백 카드나 규칙으로 이어 주면 줄어든다.
        늘어나면 카드를 추가하며 또 죽은 값을 심었다는 뜻이다.
        """
        dead = DECK_FLAGS - RULE_READ_FLAGS - CARD_READ_FLAGS
        assert len(dead) <= 15, f"죽은 표식이 늘었다: {sorted(dead)}"

    def test_the_audit_can_see_every_reader(self) -> None:
        """규칙이 읽는 표식은 **전부 `career_flags`에 이름이 있어야** 한다.

        흩어져 있으면 "누가 읽는가"를 세는 일이 문자열 검색이 되고, 그 검색이 놓친
        것이 감사에서 나온 죽은 표식이었다.
        """
        from wwe_game.domain.constants import career_rules
        from wwe_game.domain.services import championship

        assert championship.EMERGENCY_CALLUP_FLAG in RULE_READ_FLAGS
        assert career_rules.RELEASE_TRIGGER_FLAGS <= RULE_READ_FLAGS


class TestInjuryFlags:
    @staticmethod
    def chance(*flags: str) -> float:
        run = make_run().evolve(flags=frozenset(flags))
        return injury_chance(run, WeekKind.WEEKLY_SHOW)

    def test_painkillers_make_the_next_one_worse(self) -> None:
        # `CareerRun.flags`가 문서로 약속했던 규칙이다.
        assert self.chance(PAINKILLER) > self.chance()
        assert self.chance(PAINKILLER) == pytest.approx(
            self.chance() * rules.PAINKILLER_INJURY_MULTIPLIER
        )

    def test_grounding_your_style_buys_safety(self) -> None:
        assert self.chance(GROUNDED) < self.chance()

    def test_the_two_can_cancel_out(self) -> None:
        both = self.chance(PAINKILLER, GROUNDED)
        assert self.chance(GROUNDED) < both < self.chance(PAINKILLER)


class TestGrowthFlags:
    @staticmethod
    def gains(flag: str | None, stat: str, weeks: int = 400) -> int:
        from wwe_game.domain.services.week_simulation import simulate_week

        run = make_run(seed=5)
        if flag:
            run = run.evolve(flags=frozenset({flag}))
        return sum(
            simulate_week(run.evolve(week=w)).stat_delta.get(stat, 0)
            for w in range(1, weeks)
        )

    def test_a_frozen_push_slows_popularity(self) -> None:
        assert self.gains(PUSH_FROZEN, "popularity") < self.gains(None, "popularity")

    def test_a_grudge_slows_the_locker_room_back(self) -> None:
        assert self.gains(GRUDGE, "backstage") < self.gains(None, "backstage")

    def test_a_manager_speeds_up_the_mic(self) -> None:
        assert self.gains(MANAGER, "mic_work") > self.gains(None, "mic_work")


class TestRivalryFlags:
    def test_an_unfinished_nemesis_cools_slower(self) -> None:
        # 식는 것은 **가장 뜨겁지 않은 쪽**이다 — 둘을 두고 아래쪽을 본다.
        pair = (
            Rivalry("코디 로즈", RivalryStage.NEMESIS, 90, 1),
            Rivalry("건서", RivalryStage.HEATED, 50, 1),
        )
        quiet = make_run(week=50, rivalries=pair)
        locked = quiet.evolve(flags=frozenset({NEMESIS_LOCKED}))

        def cooled(run: object) -> int:
            moved = rivalry_engine.advance_rivalries(
                run, 50, 5, SeededRoll(1, 50, "riv")
            )
            return next(r.heat for r in moved if r.rival_name == "건서")

        assert cooled(locked) > cooled(quiet)
