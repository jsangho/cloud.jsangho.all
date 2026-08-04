from __future__ import annotations

import logging

from lion_king.app.dtos.receipt_dto import (
    OcrReceiptCommand,
    ReceiptDraftDto,
    ReceiptLineItemDto,
    ReceiptSummaryDto,
)
from lion_king.app.ports.input.receipt_use_case import ReceiptUseCase
from lion_king.app.ports.output.receipt_image_repository import ReceiptImageRepository
from lion_king.app.ports.output.receipt_ocr_port import ReceiptOcrPort
from lion_king.domain.entities.receipt_draft import ReceiptDraft
from lion_king.domain.services.receipt_parser import parse_receipt
from lion_king.domain.value_objects.receipt_key import ReceiptKey

logger = logging.getLogger("uvicorn.error")


class ReceiptInteractor(ReceiptUseCase):
    def __init__(self, images: ReceiptImageRepository, ocr: ReceiptOcrPort) -> None:
        self._images = images
        self._ocr = ocr

    async def list_receipts(self, *, user_id: str) -> list[ReceiptSummaryDto]:
        return await self._images.list_by_owner(user_id=user_id)

    async def read_receipt(self, command: OcrReceiptCommand) -> ReceiptDraftDto:
        # 소유권 검증이 **가장 먼저**다. 보관소를 먼저 찔러보면 남의 키의 존재
        # 여부가 응답 시간과 로그로 새어 나간다.
        receipt_key = ReceiptKey.validated(key=command.key, owner_sub=command.user_id)

        image = await self._images.load(key=receipt_key.value)
        raw = await self._ocr.read(image)
        draft = parse_receipt(raw_text=raw.raw_text, confidence=raw.confidence)

        # 원문은 재파싱·디버깅용이라 로그까지만 남긴다. 응답에는 넣지 않는다.
        logger.debug(
            "[lion_king.receipt] 판독 원문 | key=%s | text=%s",
            receipt_key.value,
            draft.raw_text,
        )
        return _to_dto(draft)


def _to_dto(draft: ReceiptDraft) -> ReceiptDraftDto:
    return ReceiptDraftDto(
        merchant_name=draft.merchant_name,
        business_no=draft.business_no,
        transacted_at=draft.transacted_at,
        total_amount=draft.total_amount,
        vat_amount=draft.vat_amount,
        currency=draft.currency,
        line_items=tuple(
            ReceiptLineItemDto(
                name=item.name,
                quantity=item.quantity,
                unit_price=item.unit_price,
                amount=item.amount,
            )
            for item in draft.line_items
        ),
        confidence=draft.confidence,
        needs_review=draft.needs_review,
    )
