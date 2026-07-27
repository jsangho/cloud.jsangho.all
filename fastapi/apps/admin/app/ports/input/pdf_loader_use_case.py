from __future__ import annotations

from abc import ABC, abstractmethod

from admin.app.dtos.pdf_loader_dto import PdfLoaderCommand, PdfLoaderResult


class PdfLoaderUseCase(ABC):
    """`/pdf/upload` inbound(pdf_loader_router) 입력 포트."""

    @abstractmethod
    async def load_and_store(self, command: PdfLoaderCommand) -> PdfLoaderResult:
        """PDF에서 텍스트를 추출해 그래프 DB에 Document 노드로 저장한다."""
        ...
