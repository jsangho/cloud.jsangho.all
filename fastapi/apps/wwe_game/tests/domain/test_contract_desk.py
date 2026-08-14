"""재계약 협상 (하네스 §3-D84).

§3-D48이 *"재계약 협상의 선택지가 없다 — 지금은 규칙이 자동 처리한다"*로 남겨 둔
자리다. 만료 주차에 `contract_office.settle`이 조용히 `renew()`를 불러 도장을 찍었고,
플레이어는 **협상이 있었다는 사실조차 몰랐다.**

여기서 지키는 것 넷:

1. 만료 주차에 협상이 **열린다** (도장이 안 찍힌다)
2. 답하기 전에는 진행이 **막힌다** — 목표(§3-D80)보다 앞선다
3. 다섯 선택지가 **각각 다르게** 동작한다 (하나라도 같으면 그건 서식이다)
4. 화면이 보여 준 금액과 **실제로 찍히는 금액이 같다**
"""

from __future__ import annotations

import pytest
from _helpers import make_run  # noqa: I001  (tests 트리에 __init__.py가 없다)
from wwe_game.domain.entities.career_run import CareerRun
from wwe_game.domain.services import (
    career_advance,
    contract_desk,
    contract_office,
    seeded_roll,
)
from wwe_game.domain.services.seeded_roll import SeededRoll
from wwe_game.domain.value_objects.advance_outcome import StopReason
from wwe_game.domain.value_objects.contract import Contract
from wwe_game.domain.value_objects.contract_offer import OFFERS, OfferChoice
from wwe_game.domain.value_objects.wrestler_stats import WrestlerStats

WEEK = 300
"""협상이 열리는 주차. `make_run`의 0주차 계약을 여기로 끌어와 만료를 만든다."""

SOLID = WrestlerStats(popularity=70, in_ring=70, mic_work=60, backstage=70)
"""잘릴 걱정이 없는 선수 — 위험권이면 협상 자체가 안 열린다(§3-D50)."""


def expiring(seed: int = 42, *, stats: WrestlerStats = SOLID) -> CareerRun:
    """만료 주차에 선 세이브. **협상은 아직 안 열렸다.**"""
    return make_run(week=WEEK, seed=seed, stats=stats).evolve(
        contract=Contract(weekly_pay=3_000, signed_week=WEEK - 104, ends_week=WEEK),
    )


def opened(seed: int = 42, *, stats: WrestlerStats = SOLID) -> CareerRun:
    """협상이 열린 세이브 — `settle`을 실제로 통과시켜 만든다.

    `offer_week`를 손으로 넣지 않는 이유: 그러면 "열리는 조건"이 테스트에서
    빠지고, 규칙이 바뀌어도 이 파일은 계속 통과한다.
    """
    run = expiring(seed, stats=stats)
    return contract_office.settle(
        run, SeededRoll(run.seed, run.week, seeded_roll.CONTRACT)
    )


class TestTheOfferOpens:
    def test_expiry_no_longer_signs_you_back_quietly(self) -> None:
        """**만료가 도장을 찍지 않는다.** 이 규칙의 존재 이유다."""
        before = expiring()
        after = opened()
        assert contract_desk.is_open(after)
        assert after.offer_week == WEEK
        # 계약은 그대로다 — 새로 맺힌 것이 없다.
        assert after.contract == before.contract

    def test_it_stays_shut_while_the_contract_runs(self) -> None:
        run = make_run(week=WEEK, stats=SOLID).evolve(
            contract=Contract(weekly_pay=3_000, signed_week=WEEK, ends_week=WEEK + 52),
        )
        settled = contract_office.settle(
            run, SeededRoll(run.seed, run.week, seeded_roll.CONTRACT)
        )
        assert not contract_desk.is_open(settled)

    def test_nobody_negotiates_with_someone_they_are_cutting(self) -> None:
        """위험권이면 오퍼가 없다 (§3-D50). 방출과 **같은 판정**을 쓴다."""
        doomed = expiring(stats=WrestlerStats(popularity=10, in_ring=20, backstage=10))
        settled = contract_office.settle(
            doomed, SeededRoll(doomed.seed, doomed.week, seeded_roll.CONTRACT)
        )
        assert not contract_desk.is_open(settled)
        assert settled.contract is None, "협상이 아니라 방출이어야 한다"


class TestItBlocksTheWeek:
    def test_advance_does_not_move_a_single_week(self) -> None:
        outcome = career_advance.advance(opened())
        assert outcome.stop_reason is StopReason.OFFER
        assert outcome.run.week == WEEK, "협상 중에 한 주라도 가면 안 된다"

    def test_the_offer_comes_before_the_quarter_goal(self) -> None:
        """**협상이 목표보다 앞선다** (§3-D84).

        계약이 없을 수도 있는데 다음 석 달에 무엇을 걸지부터 물으면 순서가
        뒤집힌다 — 무소속에는 목표를 묻지 않는다는 §3-D80과 같은 이유다.
        """
        from wwe_game.domain.services import quarter_plan

        run = opened().evolve(goal=None, goal_quarter=-1)
        assert quarter_plan.needs_goal(run), "둘 다 물어야 하는 상태를 만들어 둔다"
        assert career_advance.advance(run).stop_reason is StopReason.OFFER

    def test_answering_lets_the_week_run_again(self) -> None:
        signed = contract_desk.answer(opened(), OfferChoice.ACCEPT)
        assert not contract_desk.is_open(signed)
        assert career_advance.advance(signed).stop_reason is not StopReason.OFFER


class TestTheFiveAnswers:
    """**다섯이 각각 달라야 한다.** 넷이 "남는다"면 그건 선택이 아니라 서식이다."""

    def test_accept_signs_at_the_offered_pay(self) -> None:
        run = opened()
        signed = contract_desk.answer(run, OfferChoice.ACCEPT)
        assert signed.contract is not None
        assert signed.contract.weekly_pay == contract_desk.offered_pay(run)
        assert signed.contract.ends_week == WEEK + 3 * 52

    def test_short_and_long_differ_in_term_and_price(self) -> None:
        """**기간이 진짜 선택이다** — 짧으면 비싸고 길면 깎인다."""
        run = opened()
        short = contract_desk.answer(run, OfferChoice.SHORT).contract
        long = contract_desk.answer(run, OfferChoice.LONG).contract
        assert short is not None and long is not None
        assert short.ends_week == WEEK + 2 * 52
        assert long.ends_week == WEEK + 5 * 52
        assert short.weekly_pay > long.weekly_pay

    def test_walking_out_leaves_you_unsigned(self) -> None:
        """**`WALK`이 있어야 한다** — 스스로 무소속을 고를 수 있다 (§3-D50)."""
        gone = contract_desk.answer(opened(), OfferChoice.WALK)
        assert gone.contract is None
        assert gone.is_active, "무소속은 커리어의 끝이 아니다"
        assert not contract_desk.is_open(gone)

    def test_pushing_pays_more_when_it_lands(self) -> None:
        run = _seed_where(push_refused=False)
        pushed = contract_desk.answer(run, OfferChoice.PUSH).contract
        assert pushed is not None
        assert pushed.weekly_pay > contract_desk.offered_pay(run)

    def test_pushing_can_send_you_out_the_door(self) -> None:
        """`PUSH`의 거절이 이 화면의 긴장 전부다 — 없으면 누구나 늘 더 부른다."""
        run = _seed_where(push_refused=True)
        assert contract_desk.answer(run, OfferChoice.PUSH).contract is None

    def test_every_answer_closes_the_desk(self) -> None:
        """어느 쪽으로 답하든 협상은 닫힌다 — 안 닫히면 진행이 영영 막힌다."""
        for choice in OfferChoice:
            answered = contract_desk.answer(opened(), choice)
            assert not contract_desk.is_open(answered), f"{choice}가 협상을 안 닫았다"
            assert answered.offer_week == 0

    def test_answering_outside_a_negotiation_is_refused(self) -> None:
        from wwe_game.domain.exceptions import NoOfferOpenError

        with pytest.raises(NoOfferOpenError):
            contract_desk.answer(expiring(), OfferChoice.ACCEPT)


class TestTheScreenAndTheRuleAgree:
    def test_the_quoted_pay_is_the_pay_that_gets_signed(self) -> None:
        """**보여 준 금액과 찍힌 금액이 같다** — 어댑터가 곱셈을 다시 적지 않는 이유다."""
        run = opened()
        for spec in contract_desk.options(run):
            if spec.refusal > 0 or spec.years == 0:
                continue  # 거절·퇴사는 계약이 안 나오므로 견줄 대상이 없다
            signed = contract_desk.answer(run, spec.choice).contract
            assert signed is not None
            assert signed.weekly_pay == contract_desk.pay_for(run, spec)

    def test_walking_out_quotes_no_pay(self) -> None:
        run = opened()
        assert contract_desk.pay_for(run, OFFERS[OfferChoice.WALK]) == 0

    def test_the_offer_is_not_stored(self) -> None:
        """**제시액을 저장하지 않는다** — 그 주차 상태에서 언제든 되짚는다 (§3-D8).

        저장하면 세이브를 손댄 값과 규칙이 갈린다.
        """
        run = opened()
        assert contract_desk.offered_pay(run) == contract_office.appraise(run)


def _seed_where(*, push_refused: bool) -> CareerRun:
    """`PUSH`가 거절되는(또는 안 되는) 시드를 찾아 협상이 열린 세이브를 만든다.

    거절은 시드가 정하므로(`SeededRoll`) 고정 시드를 적어 두면 확률을 바꿨을 때
    무엇이 왜 깨졌는지 알 수 없다 — 조건으로 찾는다.
    """
    spec = OFFERS[OfferChoice.PUSH]
    for seed in range(1, 200):
        run = opened(seed)
        if not contract_desk.is_open(run):
            continue
        roll = SeededRoll(run.seed, run.week, seeded_roll.CONTRACT)
        if roll.chance(spec.refusal) is push_refused:
            return run
    raise AssertionError(f"거절={push_refused}인 시드를 못 찾았다")
