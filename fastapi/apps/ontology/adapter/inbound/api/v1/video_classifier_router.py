from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from ontology.adapter.inbound.api.schemas.video_classifier_schema import (
    VideoClassificationResponse,
    VideoTopKPredictionSchema,
)
from ontology.app.ports.input.video_classifier_use_case import VideoClassifierUseCase
from ontology.dependencies.video_classifier_provider import (
    get_video_classifier_use_case,
)

video_classifier_router = APIRouter(
    prefix="/video-classifier", tags=["video-classifier"]
)

_ALLOWED_CONTENT_TYPES = {"video/mp4", "video/webm", "video/quicktime"}


@video_classifier_router.post("/classify", response_model=VideoClassificationResponse)
async def classify_video(
    video: UploadFile = File(...),
    use_case: VideoClassifierUseCase = Depends(get_video_classifier_use_case),
) -> VideoClassificationResponse:
    if video.content_type not in _ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=422, detail="mp4, webm, mov 비디오 파일만 업로드할 수 있습니다."
        )
    content = await video.read()
    try:
        result = await use_case.classify(content)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    return VideoClassificationResponse(
        label=result.label,
        confidence=result.confidence,
        is_confident=result.is_confident,
        top5=[
            VideoTopKPredictionSchema(label=p.label, score=p.score) for p in result.top5
        ],
    )
