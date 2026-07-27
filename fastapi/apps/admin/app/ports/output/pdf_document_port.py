from __future__ import annotations

from abc import ABC, abstractmethod


class PdfDocumentPort(ABC):
    @abstractmethod
    async def save_document(
        self, *, document_id: str, filename: str, text: str
    ) -> None:
        pass
