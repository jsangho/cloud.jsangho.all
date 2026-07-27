from admin.app.ports.output.pdf_document_port import PdfDocumentPort
from neo4j import AsyncSession


class PdfDocumentRepository(PdfDocumentPort):
    """`(:Document)` 노드로 저장 — `apps/admin/_docs/neo4j-harness.md` §1 모델 참고."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def save_document(
        self, *, document_id: str, filename: str, text: str
    ) -> None:
        await self.session.run(
            """
            MERGE (d:Document {id: $document_id})
            SET d.filename = $filename,
                d.text = $text,
                d.uploaded_at = datetime()
            """,
            document_id=document_id,
            filename=filename,
            text=text,
        )
