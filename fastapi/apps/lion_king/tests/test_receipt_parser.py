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


# 실물 영수증(농협 하나로마트)의 Gemini 판독 원문. 라벨 글자 사이 공백과
# 두 줄에 걸친 품목 배치가 그대로 들어 있다 — 규칙이 무너지던 실제 사례다.
_REAL_RECEIPT = """        농협
주소:경기 의정부시
대표: 최영*             전화:031-***-****
사업자번호:127-82-*****
홈페이지 :http://www.nonghyup.com/
영수증 미지참시 교환/환불 불가(30일내)
교환/환불 구매점에서 가능(결제카드지참)
=========================================
김갑순     2015-11-03 16:31:53  0002-00085
상품(코드)            단가    수량        금액
-----------------------------------------
001 P굿모닝우유 900ML               [2,150]
*8801104210645       1,350     1       1,350
002 P양파 ,
*231973              3,300     1       3,300
003 P무 ,
*231913                500     1         500
004 P깻잎 ,
*231308                750     1         750
005 P하선정 바로먹기좋은장아찌 150g
 8801007265889       1,380     1       1,380
006 P브로커리 .
*232285              1,280     1       1,280
-----------------------------------------
                판 매 총 액:          8,560
-----------------------------------------
             ◆ 받 을 금 액 :          8,560
                신   용   액:          8,560
 ))---------------------------------------((
            부가세면세물품가액:          7,180
            부가세과세물품가액:          1,255
            부    가    세:            125
-----------------------------------------
바코드앞 * 면세, # 영세, 상품명 P포인트
-----------------------------------------
회원:2010190034*** 박*분 님
                  우수고객포인트:             40
                  잔 여 포 인 트:         14,198
                  사용가능포인트:         14,190
  ****** 신용카드 매출전표(고객용) ******
우리카드:4902************
할부:00개월              매출금액:       8,560원
승인No:75513401          가맹점:0000007490C
"""


def test_real_receipt_merchant_is_the_store_not_the_first_item() -> None:
    """상호명 줄 위에 주소·대표·전화가 끼어 있어도 상호를 집어야 한다."""
    draft = parse_receipt(raw_text=_REAL_RECEIPT, confidence=0.99)

    assert draft.merchant_name == "농협"


def test_real_receipt_ignores_barcode_as_business_number() -> None:
    """13자리 바코드 앞 10자리를 사업자번호로 오인하지 않는다. 마스킹이면 None."""
    draft = parse_receipt(raw_text=_REAL_RECEIPT, confidence=0.99)

    assert draft.business_no is None


def test_real_receipt_total_survives_spaced_out_labels() -> None:
    """`판 매 총 액:` 처럼 글자를 벌려 찍어도 합계를 찾는다."""
    draft = parse_receipt(raw_text=_REAL_RECEIPT, confidence=0.99)

    assert draft.total_amount == 8560
    assert draft.transacted_at == datetime(2015, 11, 3, 16, 31, 53)


def test_real_receipt_vat_is_not_the_exempt_supply_amount() -> None:
    """`부가세면세물품가액`(7,180)이 아니라 `부 가 세`(125)를 집는다."""
    draft = parse_receipt(raw_text=_REAL_RECEIPT, confidence=0.99)

    assert draft.vat_amount == 125


def test_real_receipt_reads_items_split_across_two_lines() -> None:
    """품목명과 단가·수량·금액이 다른 줄에 있는 배치를 읽는다."""
    draft = parse_receipt(raw_text=_REAL_RECEIPT, confidence=0.99)

    assert [item.name for item in draft.line_items] == [
        "P굿모닝우유 900ML",
        "P양파",
        "P무",
        "P깻잎",
        "P하선정 바로먹기좋은장아찌 150g",
        "P브로커리",
    ]
    assert [item.amount for item in draft.line_items] == [
        1350,
        3300,
        500,
        750,
        1380,
        1280,
    ]
    # 열 순서가 `단가 수량 금액`이다 — 수량을 1,350으로 읽으면 안 된다.
    assert draft.line_items[0].quantity == 1
    assert draft.line_items[0].unit_price == 1350


def test_real_receipt_balances_and_needs_no_review() -> None:
    """품목 합(8,560)이 합계와 맞으므로 확인 필요로 몰지 않는다."""
    draft = parse_receipt(raw_text=_REAL_RECEIPT, confidence=0.99)

    assert sum(item.amount for item in draft.line_items) == draft.total_amount
    assert draft.needs_review is False
