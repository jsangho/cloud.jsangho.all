"""파서 단위 테스트 — 고정 텍스트만 쓴다. AWS·Gemini 호출 0회."""

from __future__ import annotations

from datetime import datetime

import pytest
from lion_king.domain.services.receipt_parser import (
    ReceiptNotRecognizedError,
    parse_receipt,
    to_amount,
)

_RECEIPT = """이마트 성수점
서울특별시 성동구 아차산로 100
사업자번호 123-45-67890
2026-08-04 19:32:00

우유 1L        2     3,200     6,400
계란 30구      1     8,500     8,500

합계                          14,900
부가세                         1,354
"""


def test_parses_merchant_date_total_and_items() -> None:
    draft = parse_receipt(raw_text=_RECEIPT, confidence=0.91)

    assert draft.merchant_name == "서울특별시 성동구 아차산로 100"
    assert draft.business_no == "1234567890"
    assert draft.transacted_at == datetime(2026, 8, 4, 19, 32)
    assert draft.total_amount == 14900
    assert draft.vat_amount == 1354
    assert draft.currency == "KRW"
    assert [item.name for item in draft.line_items] == ["우유 1L", "계란 30구"]
    assert draft.line_items[0].quantity == 2
    assert draft.line_items[0].unit_price == 3200
    assert draft.line_items[0].amount == 6400


def test_item_sum_matching_total_does_not_need_review() -> None:
    draft = parse_receipt(raw_text=_RECEIPT, confidence=0.91)

    # 6,400 + 8,500 = 14,900 → 합계와 일치한다.
    assert draft.needs_review is False


@pytest.mark.parametrize(
    ("token", "expected"),
    [
        ("23,400", 23400),
        ("₩23,400", 23400),
        ("23400원", 23400),
        ("-1,000", -1000),
        ("합계", None),
        ("", None),
    ],
)
def test_amount_normalization(token: str, expected: int | None) -> None:
    """금액 변환 실패는 예외가 아니라 None이다."""
    assert to_amount(token) == expected


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("2026-08-04", datetime(2026, 8, 4)),
        ("2026/08/04 19:32", datetime(2026, 8, 4, 19, 32)),
        ("26.08.04 19:32:11", datetime(2026, 8, 4, 19, 32, 11)),
        ("2026년 8월 4일 19:32", datetime(2026, 8, 4, 19, 32)),
    ],
)
def test_date_formats(line: str, expected: datetime) -> None:
    draft = parse_receipt(raw_text=f"가게\n{line}\n합계 1,000\n", confidence=0.9)

    assert draft.transacted_at == expected


def test_invalid_date_is_left_unread_instead_of_raising() -> None:
    """13월 같은 오판독으로 500을 내지 않는다 — 확인 필요 상태로 넘긴다."""
    draft = parse_receipt(raw_text="가게\n2026-13-45\n합계 1,000\n", confidence=0.95)

    assert draft.transacted_at is None
    assert draft.needs_review is True


def test_total_falls_back_to_item_sum_when_label_missing() -> None:
    draft = parse_receipt(
        raw_text="가게\n2026-08-04\n아메리카노 1 4,500 4,500\n", confidence=0.95
    )

    assert draft.total_amount == 4500
    assert draft.needs_review is False


def test_vat_charged_separately_still_balances() -> None:
    """부가세 별도 표기 영수증도 확인 필요로 몰지 않는다."""
    draft = parse_receipt(
        raw_text=(
            "가게\n2026-08-04\n책상 1 100,000 100,000\n부가세 10,000\n합계 110,000\n"
        ),
        confidence=0.95,
    )

    assert draft.total_amount == 110000
    assert draft.needs_review is False


def test_low_confidence_needs_review() -> None:
    draft = parse_receipt(raw_text=_RECEIPT, confidence=0.5)

    assert draft.needs_review is True


def test_item_sum_mismatch_needs_review() -> None:
    draft = parse_receipt(
        raw_text="가게\n2026-08-04\n우유 1 3,000 3,000\n합계 9,900\n", confidence=0.99
    )

    assert draft.needs_review is True


@pytest.mark.parametrize("raw_text", ["", "   \n\n  ", "풍경 사진\n하늘과 바다\n"])
def test_text_without_amounts_is_not_a_receipt(raw_text: str) -> None:
    """판독 실패를 조용히 빈 초안으로 삼키지 않는다."""
    with pytest.raises(ReceiptNotRecognizedError):
        parse_receipt(raw_text=raw_text, confidence=0.9)
