from fastapi import APIRouter, Depends
from ontology.adapter.inbound.api.schemas.spam_schema import (
    SpamClassifyRequest,
    SpamClassifyResponse,
)
from ontology.app.ports.input.spam_classifier_use_case import SpamClassifierUseCase
from ontology.dependencies.spam_classifier_provider import get_spam_classifier_use_case

spam_router = APIRouter(prefix="/spam", tags=["spam"])


@spam_router.post("/classify", response_model=SpamClassifyResponse)
async def classify_spam(
    body: SpamClassifyRequest,
    use_case: SpamClassifierUseCase = Depends(get_spam_classifier_use_case),
) -> SpamClassifyResponse:
    result = await use_case.classify(subject=body.subject, body=body.body)
    return SpamClassifyResponse(
        label=result.label,
        confidence=result.confidence,
        matched_keywords=result.matched_keywords,
    )
