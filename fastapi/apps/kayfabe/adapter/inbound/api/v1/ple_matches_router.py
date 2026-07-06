from __future__ import annotations

import logging

import fastapi
from fastapi import APIRouter, Depends
from kayfabe.adapter.inbound.api.schemas.ple_events_schema import MyselfSchema
from kayfabe.adapter.inbound.api.schemas.ple_matches_schema import (
    BatchResultsRequestSchema,
    CompetitorListResponseSchema,
    CompetitorProfileResponseSchema,
    MatchResultUpdateSchema,
    PleBoardSchema,
)
from kayfabe.adapter.outbound.mappers.ple_schema_mapper import (
    batch_results_from_schema,
    board_to_schema,
    match_result_update_from_schema,
)
from kayfabe.app.dtos.ple_events_dto import MyselfQuery, MyselfResponse, MyselfUseCase
from kayfabe.app.ports.input.ple_events_use_case import PleEventsUseCase
from kayfabe.app.ports.input.ple_matches_use_case import PleMatchesUseCase
from kayfabe.dependencies.ple_events_provider import get_ple_events
from kayfabe.dependencies.ple_matches_provider import get_ple_matches

logger = logging.getLogger("uvicorn.error")

ple_matches_router = APIRouter(prefix="/ple-matches", tags=["ple-matches"])


def _ple_http_error(exc: Exception) -> fastapi.HTTPException:
    if isinstance(exc, LookupError):
        return fastapi.HTTPException(status_code=404, detail=str(exc) or "Not found")
    if isinstance(exc, ValueError):
        return fastapi.HTTPException(
            status_code=400, detail=str(exc) or "잘못된 요청입니다."
        )
    raise exc


@ple_matches_router.get("/myself", response_model=None)
async def introduce_records_myself(
    use_case: MyselfUseCase = Depends(get_ple_matches),
) -> MyselfResponse:
    schema = MyselfSchema(id=5, name="ple_matches_router")
    query = MyselfQuery(id=schema.id, name=schema.name)
    return await use_case.introduce_myself(query)


@ple_matches_router.get(
    "/competitors",
    response_model=CompetitorListResponseSchema,
    response_model_by_alias=True,
)
async def list_competitors(
    q: str | None = None,
    use_case: PleMatchesUseCase = fastapi.Depends(get_ple_matches),
):
    logger.info("[PleMatchesRouter] list_competitors | q=%s", q or "-")
    return (await use_case.list_competitors(q=q)).to_schema()


@ple_matches_router.get(
    "/competitors/{name}",
    response_model=CompetitorProfileResponseSchema,
    response_model_by_alias=True,
)
async def get_competitor_profile(
    name: str,
    use_case: PleMatchesUseCase = fastapi.Depends(get_ple_matches),
):
    logger.info("[PleMatchesRouter] get_competitor_profile | name=%s", name)
    profile = await use_case.get_competitor_profile(name)
    if not profile.matches and not await _competitor_exists(use_case, name):
        raise fastapi.HTTPException(status_code=404, detail="선수를 찾을 수 없습니다.")
    return profile.to_schema()


async def _competitor_exists(use_case: PleMatchesUseCase, name: str) -> bool:
    listed = await use_case.list_competitors()
    target = name.strip().lower()
    return any(n.lower() == target for n in listed.names)


@ple_matches_router.post(
    "/{slug}/results/batch",
    response_model=PleBoardSchema,
    response_model_by_alias=True,
)
async def set_ple_results_batch(
    slug: str,
    body: BatchResultsRequestSchema,
    use_case: PleEventsUseCase = fastapi.Depends(get_ple_events),
):
    logger.info(
        "[PleMatchesRouter] set_ple_results_batch | slug=%s count=%d",
        slug,
        len(body.results),
    )
    try:
        board = await use_case.set_match_results_batch(
            slug=slug,
            body=batch_results_from_schema(body),
        )
        return board_to_schema(board)
    except (LookupError, ValueError) as e:
        raise _ple_http_error(e) from e


@ple_matches_router.post(
    "/{slug}/matches/{match_key}/result",
    response_model=PleBoardSchema,
    response_model_by_alias=True,
)
async def set_ple_match_result(
    slug: str,
    match_key: str,
    body: MatchResultUpdateSchema,
    use_case: PleEventsUseCase = fastapi.Depends(get_ple_events),
):
    logger.info(
        "[PleMatchesRouter] set_ple_match_result | slug=%s match=%s", slug, match_key
    )
    try:
        board = await use_case.set_match_result(
            slug=slug,
            match_key=match_key,
            body=match_result_update_from_schema(body),
        )
        return board_to_schema(board)
    except (LookupError, ValueError) as e:
        raise _ple_http_error(e) from e
