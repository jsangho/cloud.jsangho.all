from pydantic import BaseModel


class SpamClassifyRequest(BaseModel):
    subject: str
    body: str


class SpamClassifyResponse(BaseModel):
    label: str
    confidence: float
    matched_keywords: list[str]
