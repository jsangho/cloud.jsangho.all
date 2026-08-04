"""영수증 판독 결과. 순수 파이썬이고, OCR 엔진도 HTTP도 모른다.

**초안(draft)이지 확정 내역이 아니다.** OCR은 틀리고, 틀렸다는 사실을 화면이 감추면
사용자는 잘못된 금액을 가계부에 그대로 남긴다. 그래서 `needs_review`가 함께 나간다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

# 이 아래로 떨어지면 사람이 확인해야 한다. 판독은 성공했지만 믿을 만하지 않은 구간.
MIN_TRUSTED_CONFIDENCE = 0.80

# 원화는 소수점이 없다. float를 쓰면 합계 검산에서 오차가 난다.
CURRENCY_KRW = "KRW"


@dataclass(frozen=True)
class ReceiptLineItem:
    """영수증 품목 한 줄. 금액은 전부 원 단위 정수다."""

    name: str
    quantity: int
    unit_price: int | None
    amount: int


@dataclass(frozen=True)
class ReceiptDraft:
    """판독된 영수증 한 장(초안)."""

    merchant_name: str | None
    business_no: str | None
    transacted_at: datetime | None
    total_amount: int | None
    vat_amount: int | None
    line_items: tuple[ReceiptLineItem, ...]
    confidence: float
    needs_review: bool
    raw_text: str
    currency: str = CURRENCY_KRW

    @classmethod
    def drafted(
        cls,
        *,
        merchant_name: str | None,
        business_no: str | None,
        transacted_at: datetime | None,
        total_amount: int | None,
        vat_amount: int | None,
        line_items: tuple[ReceiptLineItem, ...],
        confidence: float,
        raw_text: str,
    ) -> ReceiptDraft:
        """`needs_review`를 계산해서 초안을 만든다."""
        return cls(
            merchant_name=merchant_name,
            business_no=business_no,
            transacted_at=transacted_at,
            total_amount=total_amount,
            vat_amount=vat_amount,
            line_items=line_items,
            confidence=confidence,
            needs_review=_needs_review(
                transacted_at=transacted_at,
                total_amount=total_amount,
                vat_amount=vat_amount,
                line_items=line_items,
                confidence=confidence,
            ),
            raw_text=raw_text,
        )


def _needs_review(
    *,
    transacted_at: datetime | None,
    total_amount: int | None,
    vat_amount: int | None,
    line_items: tuple[ReceiptLineItem, ...],
    confidence: float,
) -> bool:
    """하나라도 걸리면 사람이 확인해야 한다."""
    if total_amount is None or transacted_at is None:
        return True
    if confidence < MIN_TRUSTED_CONFIDENCE:
        return True
    if line_items:
        items_sum = sum(item.amount for item in line_items)
        # 부가세를 합계에 포함해 적는 영수증과 별도로 적는 영수증이 둘 다 있다.
        candidates = {items_sum, items_sum + (vat_amount or 0)}
        if total_amount not in candidates:
            return True
    return False
