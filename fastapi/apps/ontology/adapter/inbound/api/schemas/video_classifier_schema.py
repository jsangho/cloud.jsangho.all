from pydantic import BaseModel


class VideoTopKPredictionSchema(BaseModel):
    label: str
    score: float


class VideoClassificationResponse(BaseModel):
    label: str
    confidence: float
    is_confident: bool
    top5: list[VideoTopKPredictionSchema]
