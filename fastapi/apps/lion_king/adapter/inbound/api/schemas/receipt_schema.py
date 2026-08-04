from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class OcrReceiptRequest(BaseModel):
    """판독 요청.

    버킷·리전·전체 S3 URI를 받지 않는다 — 임의 URI를 받으면 서버 자격증명으로
    호출자가 지정한 아무 객체나 읽어주게 된다. 키는 `POST /api/photos`가 돌려준
    값이고, 소유권은 서버가 JWT로 다시 검증한다.
    """

    key: str = Field(min_length=1, max_length=1024)


class ReceiptSummaryResponse(BaseModel):
    """목록 한 건. 필드 별칭은 저장소 관례대로 camelCase다."""

    model_config = ConfigDict(populate_by_name=True)

    key: str
    # 버킷 이름 대신 단명 presigned URL만 나간다.
    thumbnail_url: str = Field(alias="thumbnailUrl")
    captured_at: datetime | None = Field(default=None, alias="capturedAt")


class ReceiptListResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    items: list[ReceiptSummaryResponse]


class ReceiptLineItemResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str
    quantity: int
    unit_price: int | None = Field(default=None, alias="unitPrice")
    amount: int


class ReceiptDraftResponse(BaseModel):
    """판독 결과(초안).

    `rawText`는 담지 않는다 — 디버깅용이라 서버 로그(DEBUG)까지만 남긴다.
    미판독 필드는 `null`이다. `0`으로 채우면 "0원"과 구분되지 않는다.
    """

    model_config = ConfigDict(populate_by_name=True)

    merchant_name: str | None = Field(default=None, alias="merchantName")
    business_no: str | None = Field(default=None, alias="businessNo")
    transacted_at: datetime | None = Field(default=None, alias="transactedAt")
    total_amount: int | None = Field(default=None, alias="totalAmount")
    vat_amount: int | None = Field(default=None, alias="vatAmount")
    currency: str
    line_items: list[ReceiptLineItemResponse] = Field(alias="lineItems")
    confidence: float
    # 사용자 확인 없이 확정 내역처럼 다루지 말라는 신호다.
    needs_review: bool = Field(alias="needsReview")
