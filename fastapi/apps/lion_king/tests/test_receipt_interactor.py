"""유스케이스 테스트 — 포트 페이크 2개만 쓴다. AWS·Gemini 호출 0회."""

from __future__ import annotations

import pytest
from lion_king.app.dtos.receipt_dto import (
    OcrRawResult,
    OcrReceiptCommand,
    ReceiptImage,
    ReceiptSummaryDto,
)
from lion_king.app.ports.output.receipt_image_repository import (
    ObjectNotFoundError,
    ReceiptImageRepository,
)
from lion_king.app.ports.output.receipt_ocr_port import ReceiptOcrPort
from lion_king.app.use_cases.receipt_interactor import ReceiptInteractor
from lion_king.domain.value_objects.receipt_key import ReceiptKeyNotOwnedError

_RECEIPT_TEXT = (
    "이마트\n123-45-67890\n2026-08-04 19:32\n우유 2 3,200 6,400\n합계 6,400\n"
)


class FakeImages(ReceiptImageRepository):
    def __init__(self, *, missing: bool = False) -> None:
        self.missing = missing
        self.loaded: list[str] = []
        self.listed: list[str] = []

    async def list_by_owner(self, *, user_id: str) -> list[ReceiptSummaryDto]:
        self.listed.append(user_id)
        return [
            ReceiptSummaryDto(
                key=f"photos/{user_id}/a.jpg",
                thumbnail_url="https://example.test/presigned",
                captured_at=None,
            )
        ]

    async def load(self, *, key: str) -> ReceiptImage:
        self.loaded.append(key)
        if self.missing:
            raise ObjectNotFoundError(key)
        return ReceiptImage(data=b"\xff\xd8\xff", content_type="image/jpeg")


class FakeOcr(ReceiptOcrPort):
    def __init__(self, *, text: str = _RECEIPT_TEXT, confidence: float = 0.93) -> None:
        self.text = text
        self.confidence = confidence
        self.calls = 0

    async def read(self, image: ReceiptImage) -> OcrRawResult:
        self.calls += 1
        return OcrRawResult(raw_text=self.text, confidence=self.confidence)


@pytest.mark.asyncio
async def test_reads_own_receipt_into_a_draft() -> None:
    images, ocr = FakeImages(), FakeOcr()
    interactor = ReceiptInteractor(images, ocr)

    draft = await interactor.read_receipt(
        OcrReceiptCommand(user_id="42", key="photos/42/abc.jpg")
    )

    assert images.loaded == ["photos/42/abc.jpg"]
    assert draft.total_amount == 6400
    assert draft.currency == "KRW"
    assert draft.line_items[0].name == "우유"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "key",
    [
        "photos/99/abc.jpg",  # 남의 접두사
        "photos/42/../99/abc.jpg",  # 상위 이동으로 우회
        "photos/42/sub/abc.jpg",  # 하위 경로
        "photos/42/abc.pdf",  # 허용하지 않는 확장자
        "abc.jpg",  # 접두사 없음
    ],
)
async def test_foreign_key_is_rejected_before_touching_storage(key: str) -> None:
    """소유권 위반이면 S3·OCR을 **호출조차 하지 않아야** 한다."""
    images, ocr = FakeImages(), FakeOcr()
    interactor = ReceiptInteractor(images, ocr)

    with pytest.raises(ReceiptKeyNotOwnedError):
        await interactor.read_receipt(OcrReceiptCommand(user_id="42", key=key))

    assert images.loaded == []
    assert ocr.calls == 0


@pytest.mark.asyncio
async def test_missing_object_does_not_reach_the_ocr_engine() -> None:
    """없는 키에 OCR 비용을 태우지 않는다."""
    images, ocr = FakeImages(missing=True), FakeOcr()
    interactor = ReceiptInteractor(images, ocr)

    with pytest.raises(ObjectNotFoundError):
        await interactor.read_receipt(
            OcrReceiptCommand(user_id="42", key="photos/42/abc.jpg")
        )

    assert ocr.calls == 0


@pytest.mark.asyncio
async def test_listing_uses_the_token_subject_as_prefix() -> None:
    images, ocr = FakeImages(), FakeOcr()
    interactor = ReceiptInteractor(images, ocr)

    summaries = await interactor.list_receipts(user_id="42")

    assert images.listed == ["42"]
    assert summaries[0].key == "photos/42/a.jpg"
    # 목록만으로 판독이 돌면 목록 길이만큼 비용이 곱해진다.
    assert ocr.calls == 0
