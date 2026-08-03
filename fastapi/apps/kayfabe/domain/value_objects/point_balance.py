"""포인트 잔액 — 순수 계산.

프레임워크·ORM을 import하지 않는다. 여기 있는 것은 DB 없이 판단 가능한 규칙뿐이다.
배경은 `fastapi/_docs/shop-point-ledger.md` §4·§6.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PointBalance:
    """보유 포인트 = 획득액 + 원장 합계.

    잔액을 컬럼에 저장하지 않는 이유는 배점 재계산이 `earned`를 소급 변경하기 때문이다.
    `ledger_total`은 부호 있는 합계다 — 지출이 음수, 환급·지급이 양수.
    """

    earned: int
    ledger_total: int

    @property
    def balance(self) -> int:
        return self.earned + self.ledger_total

    @property
    def spent(self) -> int:
        """원장이 깎아낸 총액. `balance == earned - spent`가 항상 성립한다.

        환급·관리자 지급이 지출보다 크면 음수가 될 수 있다.
        """
        return -self.ledger_total

    def can_afford(self, price: int) -> bool:
        return self.balance >= price


def resolve_context_key(*, is_consumable: bool, context_key: str) -> str:
    """보유 행의 `context_key`를 확정한다.

    소모성 아이템은 사용 대상(예: `match:123`)이 있어야 같은 상품을 대상별로 여러 번
    살 수 있다. 영구 아이템은 빈 문자열로 통일해 유니크 제약이 중복 보유를 막게 한다.

    Postgres는 `NULL != NULL`로 취급하므로 빈 문자열이어야 하고 NULL이면 안 된다.
    """
    cleaned = context_key.strip()
    if is_consumable:
        if not cleaned:
            raise ValueError("소모성 아이템은 사용 대상(contextKey)이 필요합니다.")
        return cleaned
    return ""
