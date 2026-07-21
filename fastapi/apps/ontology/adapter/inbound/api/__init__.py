from fastapi import APIRouter
from ontology.adapter.inbound.api.v1.crawl_scrape_pipeline_router import (
    crawl_scrape_pipeline_router,
)
from ontology.adapter.inbound.api.v1.gemini_router import gemini_router
from ontology.adapter.inbound.api.v1.image_classifier_router import (
    image_classifier_router,
)
from ontology.adapter.inbound.api.v1.semantic_routing_router import (
    semantic_routing_router,
)
from ontology.adapter.inbound.api.v1.spam_router import spam_router

ontology_router = APIRouter(prefix="/ontology", tags=["ontology"])
ontology_router.include_router(spam_router)
ontology_router.include_router(gemini_router)
ontology_router.include_router(semantic_routing_router)
ontology_router.include_router(crawl_scrape_pipeline_router)
ontology_router.include_router(image_classifier_router)

__all__ = ["ontology_router"]
