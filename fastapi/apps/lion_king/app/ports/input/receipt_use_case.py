from __future__ import annotations

from abc import ABC, abstractmethod

from lion_king.app.dtos.receipt_dto import (
    OcrReceiptCommand,
    ReceiptDraftDto,
    ReceiptSummaryDto,
)


class ReceiptUseCase(ABC):
    """영수증 판독 입력 포트."""

    @abstractmethod
    async def list_receipts(self, *, user_id: str) -> list[ReceiptSummaryDto]:
        """요청자가 보관 중인 사진 목록을 최신순으로 돌려준다.

        판독은 하지 않는다 — 목록 길이만큼 OCR을 돌리면 비용과 지연이 그대로 곱해진다.
        """

    @abstractmethod
    async def read_receipt(self, command: OcrReceiptCommand) -> ReceiptDraftDto:
        """보관된 이미지 한 장을 판독해 초안을 만든다.

        요청자의 키가 아니면 `ReceiptKeyNotOwnedError`,
        보관소에 없으면 `ObjectNotFoundError`,
        영수증으로 보이지 않으면 `ReceiptNotRecognizedError`를 던진다.
        """
