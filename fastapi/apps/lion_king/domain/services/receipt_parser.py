"""OCR 텍스트 → `ReceiptDraft` 변환. 순수 함수라 AWS·Gemini 호출 없이 테스트된다.

한국 영수증의 통상 배치를 전제로 한 규칙 기반 파서다. 판독 실패(=영수증이 아님)와
"품목이 없는 영수증"은 다른 상태이므로, 전자는 예외를 던지고 후자는 빈 목록을 돌려준다.
"""

from __future__ import annotations

import re
from datetime import datetime

from lion_king.domain.entities.receipt_draft import ReceiptDraft, ReceiptLineItem


class ReceiptNotRecognizedError(Exception):
    """판독은 됐으나 영수증으로 보이지 않는다. 클라이언트에는 422."""


# 합계를 가리키는 라벨. 품목 합보다 우선한다 — 할인·봉사료가 섞이면 합이 맞지 않는다.
_TOTAL_LABELS = ("합계", "총액", "받을금액", "승인금액")
_VAT_LABELS = ("부가세", "부가가치세", "세액", "VAT")
# 품목 줄로 오해하기 쉬운 라벨들. 금액이 붙어 있어도 품목이 아니다.
_NON_ITEM_LABELS = (
    *_TOTAL_LABELS,
    *_VAT_LABELS,
    "소계",
    "공급가액",
    "과세물품가액",
    "면세물품가액",
    "받은금액",
    "거스름돈",
    "잔액",
    "할인",
    "포인트",
    "카드",
    "현금",
    "결제",
    "승인번호",
    "사업자",
    "대표",
    "주소",
    "전화",
    "TEL",
)

_BUSINESS_NO_PATTERN = re.compile(r"(\d{3})-?(\d{2})-?(\d{5})")
_DATE_PATTERN = re.compile(
    r"(?P<year>\d{4}|\d{2})[-/.](?P<month>\d{1,2})[-/.](?P<day>\d{1,2})"
    r"(?:\D{1,3}(?P<hour>\d{1,2}):(?P<minute>\d{2})(?::(?P<second>\d{2}))?)?"
)
_KOREAN_DATE_PATTERN = re.compile(
    r"(?P<year>\d{4})년\s*(?P<month>\d{1,2})월\s*(?P<day>\d{1,2})일"
    r"(?:\s*(?P<hour>\d{1,2}):(?P<minute>\d{2})(?::(?P<second>\d{2}))?)?"
)
_AMOUNT_TOKEN_PATTERN = re.compile(r"^[₩\-]?[\d,]+원?$")
# 수량으로 읽을 최대값. 이보다 크면 단가·금액으로 본다.
_MAX_QUANTITY = 999


def parse_receipt(*, raw_text: str, confidence: float) -> ReceiptDraft:
    """OCR 원문을 초안으로 만든다.

    금액이 하나도 없으면 영수증이 아니라고 보고 `ReceiptNotRecognizedError`를 던진다 —
    실패를 조용히 삼켜 빈 초안을 돌려주면 사용자는 "판독됐는데 비어 있다"로 오해한다.
    """
    lines = [line.strip() for line in raw_text.splitlines()]
    non_empty = [(index, line) for index, line in enumerate(lines) if line]
    if not non_empty:
        raise ReceiptNotRecognizedError("판독된 텍스트가 없습니다.")

    business_no, business_no_index = _find_business_no(lines)
    line_items = tuple(
        item for _, line in non_empty if (item := _to_line_item(line)) is not None
    )
    total_amount = _find_labeled_amount(non_empty, _TOTAL_LABELS)
    if total_amount is None and line_items:
        total_amount = sum(item.amount for item in line_items)

    if total_amount is None:
        raise ReceiptNotRecognizedError("금액을 찾지 못했습니다.")

    return ReceiptDraft.drafted(
        merchant_name=_find_merchant_name(lines, business_no_index),
        business_no=business_no,
        transacted_at=_find_transacted_at(non_empty),
        total_amount=total_amount,
        vat_amount=_find_labeled_amount(non_empty, _VAT_LABELS),
        line_items=line_items,
        confidence=confidence,
        raw_text=raw_text,
    )


def to_amount(token: str) -> int | None:
    """`23,400원` · `₩23,400` → `23400`. 숫자가 아니면 `None`이지 예외가 아니다."""
    cleaned = token.strip().replace(",", "").replace("₩", "").removesuffix("원")
    negative = cleaned.startswith("-")
    digits = cleaned.lstrip("-")
    if not digits.isdigit():
        return None
    value = int(digits)
    return -value if negative else value


def _find_business_no(lines: list[str]) -> tuple[str | None, int | None]:
    for index, line in enumerate(lines):
        match = _BUSINESS_NO_PATTERN.search(line)
        if match:
            return "".join(match.groups()), index
    return None, None


def _find_merchant_name(lines: list[str], business_no_index: int | None) -> str | None:
    """사업자등록번호 라인 위쪽 첫 비어있지 않은 줄 — 한국 영수증의 통상 배치다."""
    if business_no_index is not None:
        for line in reversed(lines[:business_no_index]):
            if line:
                return line
    for line in lines:
        if line:
            return line
    return None


def _find_transacted_at(non_empty: list[tuple[int, str]]) -> datetime | None:
    for _, line in non_empty:
        parsed = _parse_datetime(line)
        if parsed is not None:
            return parsed
    return None


def _parse_datetime(line: str) -> datetime | None:
    match = _KOREAN_DATE_PATTERN.search(line) or _DATE_PATTERN.search(line)
    if match is None:
        return None

    year = int(match.group("year"))
    if year < 100:
        # 영수증의 두 자리 연도는 2000년대다.
        year += 2000
    try:
        return datetime(
            year=year,
            month=int(match.group("month")),
            day=int(match.group("day")),
            hour=int(match.group("hour") or 0),
            minute=int(match.group("minute") or 0),
            second=int(match.group("second") or 0),
        )
    except ValueError:
        # 13월 같은 오판독. 날짜를 못 찾은 것으로 두면 needs_review가 켜진다.
        return None


def _find_labeled_amount(
    non_empty: list[tuple[int, str]], labels: tuple[str, ...]
) -> int | None:
    for _, line in non_empty:
        if not any(label in line for label in labels):
            continue
        amounts = [
            value
            for token in line.split()
            if _AMOUNT_TOKEN_PATTERN.match(token)
            and (value := to_amount(token)) is not None
        ]
        if amounts:
            # 라벨 줄의 마지막 숫자가 금액이다 (`합계 3건 23,400`).
            return amounts[-1]
    return None


def _to_line_item(line: str) -> ReceiptLineItem | None:
    """`우유 1L  2  3,200  6,400` 형태의 줄을 품목으로 읽는다."""
    if any(label in line for label in _NON_ITEM_LABELS):
        return None
    if _BUSINESS_NO_PATTERN.search(line) or _parse_datetime(line) is not None:
        return None

    tokens = line.split()
    if len(tokens) < 2:
        return None

    trailing: list[int] = []
    raw_trailing: list[str] = []
    while tokens and _AMOUNT_TOKEN_PATTERN.match(tokens[-1]):
        value = to_amount(tokens[-1])
        if value is None:
            break
        trailing.insert(0, value)
        raw_trailing.insert(0, tokens.pop())

    name = " ".join(tokens).strip()
    # 이름이 없거나 숫자뿐이면 품목 줄이 아니다.
    if not trailing or not name or not any(char.isalpha() for char in name):
        return None
    # 숫자가 하나뿐이면 금액처럼 적힌 것만 받는다. 그러지 않으면 주소의 번지수
    # (`… 아차산로 100`)까지 품목으로 읽혀 합계 검산이 깨진다.
    if len(trailing) == 1 and not _looks_like_money(raw_trailing[0], trailing[0]):
        return None

    quantity, unit_price, amount = _split_numbers(trailing)
    if amount is None or amount <= 0:
        return None
    return ReceiptLineItem(
        name=name, quantity=quantity, unit_price=unit_price, amount=amount
    )


def _looks_like_money(token: str, value: int) -> bool:
    """천단위 구분자·통화 표시가 있거나 네 자리 이상이면 금액으로 본다."""
    return (
        "," in token or token.endswith("원") or token.startswith("₩") or value >= 1000
    )


def _split_numbers(trailing: list[int]) -> tuple[int, int | None, int | None]:
    """줄 끝 숫자들을 (수량, 단가, 금액)으로 나눈다. 미기재 수량은 1이다."""
    if len(trailing) >= 3:
        quantity, unit_price, amount = trailing[-3], trailing[-2], trailing[-1]
        if 0 < quantity <= _MAX_QUANTITY:
            return quantity, unit_price, amount
        return 1, unit_price, amount
    if len(trailing) == 2:
        first, amount = trailing
        if 0 < first <= _MAX_QUANTITY:
            # 수량 × 단가 = 금액이 맞아떨어질 때만 단가를 되살린다.
            unit_price = amount // first if first and amount % first == 0 else None
            return first, unit_price, amount
        return 1, first, amount
    return 1, None, trailing[0]
