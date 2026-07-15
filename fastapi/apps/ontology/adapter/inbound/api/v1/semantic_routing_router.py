from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Body, Depends
from ontology.adapter.inbound.api.schemas.semantic_routing_schema import (
    RoutingDecisionResponse,
    SemanticRoutingSchema,
)
from ontology.app.dtos.semantic_routing_dto import SemanticRoutingCommand
from ontology.app.ports.input.semantic_routing_use_case import SemanticRoutingUseCase
from ontology.dependencies.semantic_routing_provider import (
    get_semantic_routing_use_case,
)

logger = logging.getLogger("uvicorn.error")

semantic_routing_router = APIRouter(prefix="/semantic-router", tags=["semantic-router"])


@semantic_routing_router.post("/route", response_model=RoutingDecisionResponse)
async def route(
    schema: Annotated[SemanticRoutingSchema, Body()],
    use_case: SemanticRoutingUseCase = Depends(get_semantic_routing_use_case),
) -> RoutingDecisionResponse:
    logger.info("[ontology/semantic-router/route] question=%s", schema.question)
    decision = await use_case.route(SemanticRoutingCommand(question=schema.question))
    return RoutingDecisionResponse(
        destination=decision.destination, entities=list(decision.entities)
    )
