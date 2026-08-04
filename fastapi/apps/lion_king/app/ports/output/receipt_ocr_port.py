from __future__ import annotations

from abc import ABC, abstractmethod

from lion_king.app.dtos.receipt_dto import OcrRawResult, ReceiptImage


class OcrUnavailableError(Exception):
    """판독 엔진 오류·한도 초과. 클라이언트에는 503."""


class ReceiptOcrPort(ABC):
    """이미지 → 텍스트 판독 출력 포트.

    유스케이스는 Textract도 Gemini도 모른다. 엔진을 바꿔도 바뀌는 것은 이 포트의
    구현체 하나뿐이다.
    """

    @abstractmethod
    async def read(self, image: ReceiptImage) -> OcrRawResult:
        """이미지에서 텍스트를 읽는다. 엔진 실패 시 `OcrUnavailableError`."""
