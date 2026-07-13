import asyncio
import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from ontology.adapter.inbound.api.schemas.vision_schema import VisionMyselfSchema
from ontology.app.dtos.face_identification_dto import FaceIdentificationResult
from ontology.app.dtos.vision_dto import (
    VisionImageUploadResult,
    VisionQuery,
    VisionResponse,
)
from ontology.app.ports.input.face_identification_use_case import (
    FaceIdentificationUseCase,
)
from ontology.app.ports.input.vision_use_case import VisionUseCase
from ontology.dependencies.face_identification_provider import (
    get_face_identification_use_case,
)
from ontology.dependencies.vision_provider import get_vision_use_case

vision_router = APIRouter(prefix="/vision", tags=["vision"])

_ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png"}


@vision_router.get("/myself")
async def introduce_myself(
    use_case: VisionUseCase = Depends(get_vision_use_case),
) -> VisionResponse:
    schema = VisionMyselfSchema()
    query = VisionQuery(id=schema.id, name=schema.name)
    return await use_case.introduce_myself(query)


@vision_router.post("/upload")
async def upload_image(
    file: UploadFile = File(...),
    use_case: VisionUseCase = Depends(get_vision_use_case),
) -> VisionImageUploadResult:
    if file.content_type not in _ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400, detail="jpg 또는 png 이미지 파일만 업로드할 수 있습니다."
        )
    content = await file.read()
    try:
        return await use_case.upload_image(
            filename=file.filename or "upload",
            content_type=file.content_type,
            content=content,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


@vision_router.post("/identify")
async def identify_face(
    file: UploadFile = File(...),
    use_case: FaceIdentificationUseCase = Depends(get_face_identification_use_case),
) -> FaceIdentificationResult:
    if file.content_type not in _ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400, detail="jpg 또는 png 이미지 파일만 업로드할 수 있습니다."
        )
    content = await file.read()
    suffix = Path(file.filename or "upload.jpg").suffix or ".jpg"
    fd, tmp_path = tempfile.mkstemp(suffix=suffix)
    try:
        os.write(fd, content)
        os.close(fd)
        return await asyncio.to_thread(use_case.identify, tmp_path)
    finally:
        os.remove(tmp_path)
