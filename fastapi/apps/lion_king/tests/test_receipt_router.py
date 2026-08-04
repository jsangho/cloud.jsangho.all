"""라우터 계층 계약 테스트 — 웹이 실제로 받는 JSON과 인증 가드를 고정한다."""

from __future__ import annotations

from datetime import datetime

import pytest
from core.security.dependencies import get_current_user
from core.security.token_verifier import TokenPayload
from fastapi.testclient import TestClient
from lion_king.adapter.inbound.api.v1.receipt_router import receipt_router
from lion_king.app.dtos.receipt_dto import (
    OcrReceiptCommand,
    ReceiptDraftDto,
    ReceiptLineItemDto,
    ReceiptSummaryDto,
)
from lion_king.app.ports.input.receipt_use_case import ReceiptUseCase
from lion_king.app.ports.output.photo_repository import PhotoStorageUnavailableError
from lion_king.app.ports.output.receipt_image_repository import ObjectNotFoundError
from lion_king.app.ports.output.receipt_ocr_port import OcrUnavailableError
from lion_king.dependencies.receipt_provider import get_receipt_use_case
from lion_king.domain.services.receipt_parser import ReceiptNotRecognizedError
from lion_king.domain.value_objects.receipt_key import ReceiptKeyNotOwnedError

from fastapi import FastAPI

_DRAFT = ReceiptDraftDto(
    merchant_name="이마트 성수점",
    business_no="1234567890",
    transacted_at=datetime(2026, 8, 4, 19, 32),
    total_amount=23400,
    vat_amount=2127,
    currency="KRW",
    line_items=(
        ReceiptLineItemDto(name="우유 1L", quantity=2, unit_price=3200, amount=6400),
    ),
    confidence=0.91,
    needs_review=False,
)


class FakeUseCase(ReceiptUseCase):
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.seen: list[OcrReceiptCommand] = []
        self.listed: list[str] = []

    async def list_receipts(self, *, user_id: str) -> list[ReceiptSummaryDto]:
        if self.error is not None:
            raise self.error
        self.listed.append(user_id)
        return [
            ReceiptSummaryDto(
                key=f"photos/{user_id}/abc.jpg",
                thumbnail_url="https://example.test/presigned",
                captured_at=datetime(2026, 8, 4, 19, 30),
            )
        ]

    async def read_receipt(self, command: OcrReceiptCommand) -> ReceiptDraftDto:
        if self.error is not None:
            raise self.error
        self.seen.append(command)
        return _DRAFT


def _claims(sub: str = "42") -> TokenPayload:
    return TokenPayload(
        sub=sub,
        aud="jsangho-api",
        exp=9999999999,
        iat=0,
        jti="jti",
        roles=["user"],
        platform="web",
        device_id="d1",
    )


def _client(use_case: FakeUseCase, *, authenticated: bool = True) -> TestClient:
    app = FastAPI()
    app.include_router(receipt_router, prefix="/api")
    app.dependency_overrides[get_receipt_use_case] = lambda: use_case
    if authenticated:
        app.dependency_overrides[get_current_user] = _claims
    return TestClient(app)


def test_list_returns_camel_case_fields() -> None:
    response = _client(FakeUseCase()).get("/api/receipts")

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert set(item) == {"key", "thumbnailUrl", "capturedAt"}


def test_draft_returns_camel_case_fields_without_raw_text() -> None:
    """rawText는 디버깅용이라 응답에 나가지 않는다."""
    response = _client(FakeUseCase()).post(
        "/api/receipts/ocr", json={"key": "photos/42/abc.jpg"}
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "merchantName",
        "businessNo",
        "transactedAt",
        "totalAmount",
        "vatAmount",
        "currency",
        "lineItems",
        "confidence",
        "needsReview",
    }
    assert body["totalAmount"] == 23400
    assert body["lineItems"][0]["unitPrice"] == 3200


def test_user_id_comes_from_the_token_not_the_request() -> None:
    """클라이언트가 소유자를 지정할 수 없어야 남의 사진을 못 읽는다."""
    use_case = FakeUseCase()

    _client(use_case).post(
        "/api/receipts/ocr",
        json={"key": "photos/42/abc.jpg", "userId": "99", "user_id": "99"},
    )

    assert use_case.seen[0].user_id == "42"


@pytest.mark.parametrize("path", ["/api/receipts", "/api/receipts/ocr"])
def test_unauthenticated_requests_are_rejected(path: str) -> None:
    """무인증 판독은 우리 자격증명으로 S3를 읽고 OCR 비용을 태우는 입구가 된다."""
    use_case = FakeUseCase()
    client = _client(use_case, authenticated=False)

    response = (
        client.get(path)
        if path == "/api/receipts"
        else client.post(path, json={"key": "photos/42/abc.jpg"})
    )

    assert response.status_code == 401
    assert use_case.seen == []
    assert use_case.listed == []


@pytest.mark.parametrize(
    ("error", "status"),
    [
        (ReceiptKeyNotOwnedError("photos/99/abc.jpg"), 404),
        (ObjectNotFoundError("photos/42/abc.jpg"), 404),
        (ReceiptNotRecognizedError("풍경"), 422),
        (PhotoStorageUnavailableError("no bucket"), 503),
        (OcrUnavailableError("quota exceeded"), 503),
    ],
)
def test_errors_map_to_status_codes(error: Exception, status: int) -> None:
    response = _client(FakeUseCase(error=error)).post(
        "/api/receipts/ocr", json={"key": "photos/42/abc.jpg"}
    )

    assert response.status_code == status
    # 내부 사정(버킷·엔진 오류 원문)이 새어 나가면 안 된다.
    assert "bucket" not in response.text
    assert "quota" not in response.text


def test_storage_failure_on_list_is_503() -> None:
    response = _client(
        FakeUseCase(error=PhotoStorageUnavailableError("no bucket"))
    ).get("/api/receipts")

    assert response.status_code == 503
    assert "bucket" not in response.text


def test_missing_key_is_rejected() -> None:
    assert _client(FakeUseCase()).post("/api/receipts/ocr", json={}).status_code == 422
