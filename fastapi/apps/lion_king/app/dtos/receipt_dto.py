from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class OcrReceiptCommand:
    """판독 요청 한 건.

    `user_id`는 **JWT에서 꺼낸 값**이다. 클라이언트가 보낸 값을 쓰면 남의 사진을
    우리 자격증명으로 읽어주게 된다.
    """

    user_id: str
    key: str


@dataclass(frozen=True)
class ReceiptImage:
    """보관소에서 꺼낸 이미지 한 장."""

    data: bytes
    content_type: str


@dataclass(frozen=True)
class OcrRawResult:
    """엔진 중립 판독 결과.

    Textract든 Gemini든 이 모양으로 맞춰서 돌려준다 — 벤더 응답 원형이 유스케이스로
    새어 들어오면 엔진을 바꿀 때 유스케이스까지 함께 뜯어야 한다.
    """

    raw_text: str
    confidence: float


@dataclass(frozen=True)
class ReceiptSummaryDto:
    """목록 한 건. `thumbnail_url`은 단명 presigned URL이고 버킷 이름은 담기지 않는다."""

    key: str
    thumbnail_url: str
    captured_at: datetime | None


@dataclass(frozen=True)
class ReceiptLineItemDto:
    name: str
    quantity: int
    unit_price: int | None
    amount: int


@dataclass(frozen=True)
class ReceiptDraftDto:
    """API로 나가는 초안. `raw_text`는 담지 않는다 — 디버깅용이라 서버 로그까지만."""

    merchant_name: str | None
    business_no: str | None
    transacted_at: datetime | None
    total_amount: int | None
    vat_amount: int | None
    currency: str
    line_items: tuple[ReceiptLineItemDto, ...]
    confidence: float
    needs_review: bool
