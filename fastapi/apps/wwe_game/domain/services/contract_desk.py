"""재계약 협상 (하네스 §3-D84).

`contract_office.settle`이 만료 주차에 조용히 `renew()`를 부르던 자리를 갈랐다.
이제 만료가 오면 **협상이 열리고**(`offer_week`), 플레이어가 답할 때까지 진행이
막힌다 — §3-D80의 분기 목표와 같은 모양이다.

**위험권이면 협상이 안 열린다.** 잘릴 사람에게는 오퍼가 없다(§3-D50) — 그 판정은
`contract_office`가 이미 하고 있고 여기서 다시 하지 않는다.
"""

from __future__ import annotations

from wwe_game.domain.entities.career_run import CareerRun
from wwe_game.domain.exceptions import NoOfferOpenError
from wwe_game.domain.services import contract_office, seeded_roll
from wwe_game.domain.services.seeded_roll import SeededRoll
from wwe_game.domain.value_objects.contract import Contract
from wwe_game.domain.value_objects.contract_offer import (
    OFFERS,
    OfferChoice,
    OfferSpec,
    spec_of,
)

WEEKS_PER_YEAR = 52


def is_open(run: CareerRun) -> bool:
    """협상이 열려 있는가 — 답하기 전에는 진행이 막힌다."""
    return run.is_active and run.offer_week > 0


def offered_pay(run: CareerRun) -> int:
    """단체가 부르는 주급. **지금 몸값 그대로다** — 저장하지 않고 되짚는다."""
    return contract_office.appraise(run)


def options(run: CareerRun) -> tuple[OfferSpec, ...]:
    return tuple(OFFERS.values())


def pay_for(run: CareerRun, spec: OfferSpec) -> int:
    """그 선택지로 도장을 찍으면 주급이 얼마인가. 계약을 안 맺는 선택지는 0이다.

    **화면도 이 함수를 읽는다** (`career_schema.to_offer_options`). 도메인은 배수를
    들고 있고 화면은 금액을 보여 줘야 하는데, 어댑터가 곱셈을 다시 적으면 언젠가
    "보여 준 금액과 찍힌 금액이 다르다"가 된다.
    """
    if spec.years == 0:
        return 0
    return max(1, round(offered_pay(run) * spec.pay_factor))


def answer(run: CareerRun, choice: OfferChoice) -> CareerRun:
    """협상에 답한다 (§3-D84).

    **거절과 나가기는 같은 곳으로 간다** — 무소속이다. 다른 것은 내가 골랐는지
    상대가 등을 돌렸는지뿐이고, 그 차이는 서술이 말한다.
    """
    if not is_open(run):
        raise NoOfferOpenError("지금은 협상 중이 아닙니다.")
    spec = spec_of(choice)
    cleared = run.evolve(offer_week=0)
    if spec.years == 0:
        return contract_office.release(cleared)
    roll = SeededRoll(run.seed, run.week, seeded_roll.CONTRACT)
    if spec.refusal > 0 and roll.chance(spec.refusal):
        # 등을 돌렸다 — §3-D50의 무소속 구간으로 나간다.
        return contract_office.release(cleared)
    pay = pay_for(run, spec)
    return cleared.evolve(
        contract=Contract(
            weekly_pay=pay,
            signed_week=run.week,
            ends_week=run.week + spec.years * WEEKS_PER_YEAR,
        ),
        unsigned_weeks=0,
    )
