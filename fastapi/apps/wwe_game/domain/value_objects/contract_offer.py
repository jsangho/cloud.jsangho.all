"""재계약 협상의 선택지 (하네스 §3-D84).

§3-D48에 *"재계약 협상의 선택지가 없다 — 지금은 규칙이 자동 처리한다"*로 남아 있던
자리다. 만료 주차가 오면 `contract_office.settle`이 조용히 `renew()`를 불러 도장을
찍었고, 플레이어는 그 사실조차 몰랐다.

## 왜 값이 아니라 확률을 사는가

§3-D80과 같은 원칙이다 — **돈이 스탯을 직접 사면 안 된다**(§13-Q13·§3-D41에서 두 번
겪은 사고). 여기서 거는 것은 주급이라 그 원칙에 걸리지 않지만, 대신 **거절 위험**을
붙였다: 더 부르면 더 받되 무소속이 될 수 있다.

## 기간이 진짜 선택이다

장기는 지금 몸값을 오래 붙들고, 단기는 다음 협상을 빨리 부른다. **오르는 중이면
단기가 이롭고 내리막이면 장기가 이롭다** — 그 판단이 이 선택의 전부다.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final


class OfferChoice(StrEnum):
    ACCEPT = "accept"
    """제시액을 그대로 받는다."""
    PUSH = "push"
    """더 부른다. 거절당하면 무소속이다."""
    SHORT = "short"
    """짧게 맺는다 — 다음 협상이 일찍 온다."""
    LONG = "long"
    """길게 맺는다 — 지금 조건을 오래 붙든다."""
    WALK = "walk"
    """도장을 안 찍는다. 스스로 무소속을 고른다."""


@dataclass(frozen=True)
class OfferSpec:
    choice: OfferChoice
    label: str
    blurb: str
    pay_factor: float
    """제시 주급에 곱하는 값."""
    years: int
    """계약 연수. 0이면 계약을 안 맺는다."""
    refusal: float
    """단체가 거절할 확률. 거절이면 무소속으로 나간다 (§3-D50)."""


_C = OfferChoice

OFFERS: Final[dict[OfferChoice, OfferSpec]] = {
    _C.ACCEPT: OfferSpec(
        _C.ACCEPT, "받아들인다", "제시한 조건 그대로 도장을 찍는다.", 1.0, 3, 0.0
    ),
    _C.PUSH: OfferSpec(
        _C.PUSH,
        "더 부른다",
        "몸값보다 높게 요구한다. 단체가 등을 돌릴 수 있다.",
        1.30,
        3,
        0.28,
    ),
    _C.SHORT: OfferSpec(
        _C.SHORT,
        "짧게 맺는다",
        "2년. 오르는 중이라면 다음 협상이 빨리 온다.",
        1.05,
        2,
        0.05,
    ),
    _C.LONG: OfferSpec(
        _C.LONG,
        "길게 맺는다",
        "5년. 조건은 조금 깎이지만 흔들리지 않는다.",
        0.92,
        5,
        0.0,
    ),
    _C.WALK: OfferSpec(
        _C.WALK, "나간다", "도장을 찍지 않고 무소속이 된다.", 0.0, 0, 0.0
    ),
}
"""**`WALK`이 있어야 한다.** 다섯 중 넷이 "남는다"면 그건 선택이 아니라 서식이다 —
§3-D50이 방출 뒤의 길을 이미 열어 뒀으므로, 스스로 그 길을 고를 수도 있어야 한다.

`PUSH`의 거절 확률(0.28)이 이 화면의 긴장 전부다. 넷에 한 번쯤 등을 돌리면 "더
불러 볼까"가 진짜 도박이 되고, 0.05면 누구나 늘 더 부른다.
"""


def spec_of(choice: OfferChoice) -> OfferSpec:
    return OFFERS[choice]
