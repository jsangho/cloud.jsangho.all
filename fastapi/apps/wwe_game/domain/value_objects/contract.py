"""계약 — 얼마를 받고, 언제까지인가 (하네스 §3-D47).

**계약은 상태이지 사건이 아니다.** 사건(재계약·방출·복귀 오퍼)은 서비스가 판정하고,
여기 사는 것은 그 결과로 들고 다니는 값뿐이다 — 주급과 만료 주차.

## 왜 주급인가

이 게임의 시간 단위가 주차라서다. 연봉으로 두면 주차마다 52로 나눠야 하고, 나눈
나머지가 어디로 가는지를 규칙마다 다시 정해야 한다. 화면이 연봉으로 읽고 싶으면
곱하면 된다 — 곱셈은 손실이 없다.

## 무소속에는 계약이 없다

방출된 선수는 `contract=None`이다(§3-D48). 주급 0짜리 계약을 만들어 두는 쪽이
코드가 짧지만, 그러면 "계약이 있다"가 아무 뜻도 없어진다 — 만료도 재계약도 오퍼도
전부 "계약이 있는가"에서 갈린다.
"""

from __future__ import annotations

from dataclasses import dataclass

from wwe_game.domain.exceptions import InvalidCareerRunError

WEEKS_PER_YEAR = 52

DEBUT_WEEKLY_PAY = 1_300
"""데뷔 계약의 주급(달러) — 연 $67,600.

**몸값 산식을 거치지 않는다.** 육성 계약은 협상의 결과가 아니라 정해진 액수라서다.
스무 살에 아무 이력도 없는 선수를 다섯 재료로 재 봐야 전부 바닥값이고, 그 계산은
`contract_office`가 `career_run`을 import하게 만들어 순환을 낸다. 값은 산식의
바닥(`BASE_WEEKLY_PAY`)과 같게 맞춰 뒀다 — 어긋나면 데뷔 직후 재계약이 이상해진다.
"""

DEBUT_CONTRACT_WEEKS = 3 * WEEKS_PER_YEAR
"""데뷔 계약 기간 — 3년. 첫 재계약이 스물셋에 온다."""


@dataclass(frozen=True)
class Contract:
    """지금 맺고 있는 계약 한 장."""

    weekly_pay: int
    """주급(달러). 몸값 산식이 정한다 — `contract_office.appraise()`."""
    signed_week: int
    """맺은 주차. 재계약 협상이 "이 조건으로 몇 년을 살았는지"를 읽는다."""
    ends_week: int
    """만료 주차. **이 주차가 되면 협상 이벤트가 뜬다** (§3-D49)."""

    def __post_init__(self) -> None:
        if self.weekly_pay <= 0:
            raise InvalidCareerRunError(
                f"주급은 1 이상이어야 합니다: {self.weekly_pay}"
            )
        if self.signed_week < 0:
            raise InvalidCareerRunError(
                f"체결 주차는 음수일 수 없습니다: {self.signed_week}"
            )
        if self.ends_week <= self.signed_week:
            raise InvalidCareerRunError(
                f"만료가 체결보다 뒤여야 합니다: {self.signed_week} → {self.ends_week}"
            )

    @property
    def annual_pay(self) -> int:
        """연봉. 화면이 읽는 값이라 여기서 한 번만 곱한다."""
        return self.weekly_pay * WEEKS_PER_YEAR

    @property
    def years(self) -> int:
        """계약 연수. 내림한다 — 3.9년짜리는 3년 계약으로 말한다."""
        return (self.ends_week - self.signed_week) // WEEKS_PER_YEAR

    def expires_at(self, week: int) -> bool:
        """그 주차에 만료되는가. **넘어선 경우도 참이다** — 협상 주차를 부상으로
        건너뛰면 만료가 조용히 지나가 계약 없이 뛰게 된다."""
        return week >= self.ends_week
