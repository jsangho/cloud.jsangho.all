from __future__ import annotations

import os
import tempfile
from pathlib import Path

from admin.app.dtos.pdf_loader_dto import PdfLoaderCommand, PdfLoaderResult
from admin.app.ports.input.pdf_loader_use_case import PdfLoaderUseCase
from admin.app.ports.output.pdf_document_port import PdfDocumentPort
from neo4j_graphrag.experimental.components.data_loader import PdfLoader


class PdfLoaderInteractor(PdfLoaderUseCase):
    """`PdfLoader`(neo4j_graphrag)로 PDF 텍스트를 추출해 그래프 DB에 저장한다."""

    def __init__(self, repository: PdfDocumentPort):
        self.repository = repository

    async def load_and_store(self, command: PdfLoaderCommand) -> PdfLoaderResult:
        fd, tmp_path = tempfile.mkstemp(suffix=".pdf")
        try:
            os.close(fd)
            Path(tmp_path).write_bytes(command.content)
            document = await PdfLoader().run(filepath=Path(tmp_path))
        finally:
            os.remove(tmp_path)

        document_id = document.document_info.uid
        text = document.text

        await self.repository.save_document(
            document_id=document_id, filename=command.filename, text=text
        )

        return PdfLoaderResult(
            document_id=document_id,
            filename=command.filename,
            text=text,
            char_count=len(text),
        )
