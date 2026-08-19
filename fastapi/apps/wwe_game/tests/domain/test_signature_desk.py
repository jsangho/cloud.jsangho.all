"""이름은 돈으로 산다 (하네스 §3-D92).

지키는 것 넷:

1. **한 칸으로 시작한다** — 데뷔하자마자 셋을 들고 있으면 "내 기술을 갖는" 순간이 없다
2. **칸과 이름은 다른 구매다** — 칸은 자리이고 이름은 그 위의 글자다
3. **판정에 안 닿는다** — 사는 것은 화면에 뭐라고 적히는가뿐이다 (§13-Q13)
4. **못 사면 아무 일도 안 일어난다** — 잔액이 모자라면 이름도 칸도 그대로다
"""

from __future__ import annotations

import pytest
from _helpers import make_run  # noqa: I001  (tests 트리에 __init__.py가 없다)
from wwe_game.domain.entities.career_run import CareerRun
from wwe_game.domain.exceptions import CannotNameError, InvalidFinisherNameError
from wwe_game.domain.services import signature_desk

RICH = 500_000


def rich(money: int = RICH) -> CareerRun:
    return make_run().evolve(money=money)


class TestEveryoneStartsWithOne:
    def test_a_fresh_career_has_one_slot(self) -> None:
        assert signature_desk.slots(make_run()) == signature_desk.BASE_SLOTS

    def test_an_old_save_reads_as_one(self) -> None:
        """옛 세이브는 0이다 — **0을 한 칸으로 읽어야** 동작이 안 변한다."""
        assert signature_desk.slots(make_run().evolve(signature_slots=0)) == 1

    def test_nobody_starts_with_a_name(self) -> None:
        assert make_run().signature_names == ()


class TestBuyingASlot:
    def test_it_costs_and_opens(self) -> None:
        run = rich()
        cost = signature_desk.expand_cost(run)
        assert cost is not None
        opened = signature_desk.expand(run)
        assert signature_desk.slots(opened) == signature_desk.slots(run) + 1
        assert opened.money == run.money - cost

    def test_each_slot_costs_more_than_the_last(self) -> None:
        """칸이 늘 때마다 그 뒤 모든 경기의 시그니처 빈도가 오른다 (§3-D91)."""
        run = rich()
        paid = []
        while (cost := signature_desk.expand_cost(run)) is not None:
            paid.append(cost)
            run = signature_desk.expand(run)
        assert paid == sorted(paid)
        assert len(set(paid)) == len(paid)

    def test_it_stops_at_the_ceiling(self) -> None:
        run = rich()
        while signature_desk.expand_cost(run) is not None:
            run = signature_desk.expand(run)
        assert signature_desk.slots(run) == signature_desk.MAX_SLOTS
        with pytest.raises(CannotNameError):
            signature_desk.expand(run)

    def test_an_empty_wallet_buys_nothing(self) -> None:
        with pytest.raises(CannotNameError):
            signature_desk.expand(rich(money=0))


class TestNamingASlot:
    def test_the_name_lands_in_the_slot(self) -> None:
        named = signature_desk.name_slot(rich(), 0, "붉은 손")
        assert named.signature_names == ("붉은 손",)

    def test_it_costs(self) -> None:
        run = rich()
        named = signature_desk.name_slot(run, 0, "붉은 손")
        assert named.money == run.money - signature_desk.SIGNATURE_NAMING

    def test_a_slot_that_is_not_open_refuses(self) -> None:
        """**안 산 칸에는 못 새긴다** — 칸이 자리이고 이름이 그 위의 글자다."""
        with pytest.raises(CannotNameError):
            signature_desk.name_slot(rich(), 1, "두 번째")

    def test_the_bought_slot_can_be_named(self) -> None:
        run = signature_desk.expand(rich())
        named = signature_desk.name_slot(run, 1, "두 번째")
        assert named.signature_names == ("두 번째",)

    def test_two_slots_never_share_a_name(self) -> None:
        """경기 중에 같은 이름이 두 번 불리면 칸을 산 뜻이 없다."""
        run = signature_desk.name_slot(signature_desk.expand(rich()), 0, "붉은 손")
        with pytest.raises(CannotNameError):
            signature_desk.name_slot(run, 1, "붉은 손")

    def test_the_name_rule_is_the_ring_name_rule(self) -> None:
        """§3-D12와 같은 입구다 — 서술 슬롯으로 들어가는 이름이기 때문이다."""
        with pytest.raises(InvalidFinisherNameError):
            signature_desk.name_slot(rich(), 0, "한 줄\n두 줄")

    def test_an_empty_wallet_names_nothing(self) -> None:
        run = rich(money=signature_desk.SIGNATURE_NAMING - 1)
        with pytest.raises(CannotNameError):
            signature_desk.name_slot(run, 0, "붉은 손")
        assert run.signature_names == ()


class TestDropping:
    def test_it_clears_the_name_without_a_refund(self) -> None:
        """**산 것은 이름이다** — 지운다고 되사지 않는다."""
        named = signature_desk.name_slot(rich(), 0, "붉은 손")
        dropped = signature_desk.drop_slot(named, 0)
        assert dropped.signature_names == ()
        assert dropped.money == named.money

    def test_an_empty_slot_refuses(self) -> None:
        with pytest.raises(CannotNameError):
            signature_desk.drop_slot(rich(), 0)


class TestItDoesNotTouchTheRules:
    def test_nothing_but_money_and_names_moves(self) -> None:
        """§13-Q13이 두 번 막은 지름길 — **돈이 스탯을 사지 않는다.**"""
        run = rich()
        after = signature_desk.name_slot(signature_desk.expand(run), 1, "붉은 손")
        assert after.stats == run.stats
        assert after.condition == run.condition
        assert after.week == run.week
