"""생활비 (하네스 §3-D89).

§3-D48이 *"돈의 소비처가 없다"*로 남긴 자리의 나머지. §3-D80이 분기 목표에 값을 붙여
절반을 닫았지만 잔액은 여전히 쌓이기만 했다 — 실측 60판에서 `safe`가 $17.6M을 남겼다.

여기서 지키는 것 넷:

1. **아무것도 사지 않는다** — 마모를 사는 안은 접었다(판정을 사는 것이 된다)
2. **씀씀이는 이름값을 따라간다** — 그래야 무소속이 위험해진다
3. **빚은 만들지 않는다** — 0에서 멈춘다
4. **판정에 안 닿는다** — 실측에서 인기·경기력·대관·완주율이 전부 그대로였다
"""

from __future__ import annotations

from _helpers import make_run  # noqa: I001  (tests 트리에 __init__.py가 없다)
from wwe_game.domain.entities.career_run import CareerRun, EndReason
from wwe_game.domain.services import career_advance, expenses
from wwe_game.domain.value_objects.wrestler_stats import WrestlerStats


def rich(popularity: int = 70, money: int = 1_000_000) -> CareerRun:
    return make_run(week=300, stats=WrestlerStats(popularity=popularity)).evolve(
        money=money
    )


class TestItCostsMoreToBeFamous:
    def test_the_cost_rises_with_the_name(self) -> None:
        """**수입이 아니라 이름값을 따라간다** — 그래야 무소속이 위험해진다."""
        assert expenses.weekly_cost(rich(popularity=90)) > expenses.weekly_cost(
            rich(popularity=30)
        )

    def test_even_a_nobody_spends_something(self) -> None:
        assert expenses.weekly_cost(rich(popularity=0)) == expenses.LIVING_BASE

    def test_a_closed_career_spends_nothing(self) -> None:
        closed = rich().ended(EndReason.PLAYER)
        assert expenses.weekly_cost(closed) == 0
        assert expenses.settle(closed).money == closed.money

    def test_it_does_not_look_at_the_wallet(self) -> None:
        """**"돈이 없으면 덜 쓴다"가 되면 이 규칙이 스스로를 무력화한다.**"""
        broke = rich(money=0)
        loaded = rich(money=9_000_000)
        assert expenses.weekly_cost(broke) == expenses.weekly_cost(loaded)

    def test_it_does_not_look_at_the_contract(self) -> None:
        """무소속이 되어도 씀씀이는 그대로다 — 그것이 이 절의 전부다 (§3-D50)."""
        signed = rich()
        loose = signed.evolve(contract=None)
        assert expenses.weekly_cost(loose) == expenses.weekly_cost(signed)


class TestNoDebt:
    def test_the_balance_stops_at_zero(self) -> None:
        """빚을 허용하면 새 축이 하나 생긴다 — 얼마부터 위험한지, 갚는 길은 무엇인지."""
        broke = rich(money=10)
        assert expenses.settle(broke).money == 0

    def test_it_never_goes_below(self) -> None:
        assert expenses.settle(rich(money=0)).money == 0


class TestItRunsInsideTheOneTidyUp:
    """**뒷정리 순서는 `settle_week` 하나다** — 밖에서 다시 적으면 갈린다."""

    def test_a_settled_week_spends(self) -> None:
        run = rich(money=1_000_000)
        after = career_advance.settle_week(run, run.week)
        assert after.money < run.money

    def test_the_spend_matches_the_quoted_cost(self) -> None:
        run = rich(money=1_000_000)
        after = career_advance.settle_week(run, run.week)
        assert run.money - after.money == expenses.weekly_cost(run)


class TestItTouchesNothingElse:
    def test_only_money_moves(self) -> None:
        """실측(60판)에서 인기·경기력·평판·대관·완주율·종료 사유가 전부 그대로였다."""
        run = rich()
        after = expenses.settle(run)
        assert after.stats == run.stats
        assert after.condition == run.condition
        assert after.week == run.week
        assert after.contract == run.contract
        assert after.titles_held == run.titles_held
