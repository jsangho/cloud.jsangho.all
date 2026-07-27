from admin.adapter.inbound.api.schemas.pdf_loader_schema import (
    PdfLoaderResponseSchema,
)
from admin.app.dtos.pdf_loader_dto import PdfLoaderCommand
from admin.app.ports.input.pdf_loader_use_case import PdfLoaderUseCase
from admin.dependencies.pdf_loader_provider import get_pdf_loader_use_case

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

pdf_loader_router = APIRouter(prefix="/pdf", tags=["pdf"])

_ALLOWED_CONTENT_TYPE = "application/pdf"


@pdf_loader_router.post("/upload", response_model=PdfLoaderResponseSchema)
async def upload_pdf(
    file: UploadFile = File(...),
    use_case: PdfLoaderUseCase = Depends(get_pdf_loader_use_case),
) -> PdfLoaderResponseSchema:
    if file.content_type != _ALLOWED_CONTENT_TYPE:
        raise HTTPException(status_code=422, detail="PDF 파일만 업로드할 수 있습니다.")

    content = await file.read()
    command = PdfLoaderCommand(filename=file.filename or "unknown.pdf", content=content)
    result = await use_case.load_and_store(command)

    return PdfLoaderResponseSchema(
        document_id=result.document_id,
        filename=result.filename,
        text=result.text,
        char_count=result.char_count,
    )
