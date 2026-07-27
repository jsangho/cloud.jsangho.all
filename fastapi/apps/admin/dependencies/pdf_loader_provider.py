from admin.adapter.outbound.repositories.pdf_document_repository import (
    PdfDocumentRepository,
)
from admin.app.ports.input.pdf_loader_use_case import PdfLoaderUseCase
from admin.app.ports.output.pdf_document_port import PdfDocumentPort
from admin.app.use_cases.pdf_loader_interactor import PdfLoaderInteractor
from core.matrix.grid_architect_graph_manager import get_neo4j_session
from neo4j import AsyncSession

from fastapi import Depends


def get_pdf_document_repository(
    session: AsyncSession = Depends(get_neo4j_session),
) -> PdfDocumentPort:
    return PdfDocumentRepository(session=session)


def get_pdf_loader_use_case(
    repository: PdfDocumentPort = Depends(get_pdf_document_repository),
) -> PdfLoaderUseCase:
    return PdfLoaderInteractor(repository=repository)
