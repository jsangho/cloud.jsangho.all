from pydantic import BaseModel


class TopKPredictionSchema(BaseModel):
    label: str
    score: float


class ImageClassificationResponse(BaseModel):
    label: str
    confidence: float
    is_confident: bool
    top5: list[TopKPredictionSchema]
