from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from ontology.adapter.inbound.api.schemas.image_classifier_schema import (
    ImageClassificationResponse,
    TopKPredictionSchema,
)
from ontology.app.ports.input.image_classifier_use_case import ImageClassifierUseCase
from ontology.dependencies.image_classifier_provider import (
    get_image_classifier_use_case,
)

image_classifier_router = APIRouter(
    prefix="/image-classifier", tags=["image-classifier"]
)

_ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png"}


@image_classifier_router.post("/classify", response_model=ImageClassificationResponse)
async def classify_image(
    image: UploadFile = File(...),
    use_case: ImageClassifierUseCase = Depends(get_image_classifier_use_case),
) -> ImageClassificationResponse:
    if image.content_type not in _ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=422, detail="jpg 또는 png 이미지 파일만 업로드할 수 있습니다."
        )
    content = await image.read()
    try:
        result = await use_case.classify(content)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    return ImageClassificationResponse(
        label=result.label,
        confidence=result.confidence,
        is_confident=result.is_confident,
        top5=[TopKPredictionSchema(label=p.label, score=p.score) for p in result.top5],
    )
