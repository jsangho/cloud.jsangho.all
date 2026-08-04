from __future__ import annotations

from lion_king.adapter.outbound.gemini_ocr_reader import GeminiOcrReader
from lion_king.adapter.outbound.repositories.receipt_image_s3_repository import (
    ReceiptImageS3Repository,
)
from lion_king.app.ports.input.receipt_use_case import ReceiptUseCase
from lion_king.app.use_cases.receipt_interactor import ReceiptInteractor


def get_receipt_use_case() -> ReceiptUseCase:
    return ReceiptInteractor(ReceiptImageS3Repository(), GeminiOcrReader())
