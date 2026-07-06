from fastapi import APIRouter
from ontology.adapter.inbound.api.v1.spam_router import spam_router

ontology_router = APIRouter(prefix="/ontology", tags=["ontology"])
ontology_router.include_router(spam_router)

__all__ = ["ontology_router"]
