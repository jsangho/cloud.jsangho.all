from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from kayfabe.adapter.inbound.api.schemas.ple_events_schema import MyselfSchema
from kayfabe.adapter.inbound.api.schemas.ple_match_pick_schema import (
    BatchPredictionRequestSchema,
    LinkPredictionsSchema,
    PleBoardSchema,
    PredictionRequestSchema,
    RankingsResponseSchema,
)
from kayfabe.adapter.outbound.mappers.ple_schema_mapper import (
    batch_prediction_from_schema,
    board_to_schema,
    prediction_from_schema,
)
from kayfabe.adapter.outbound.mappers.ranking_schema_mapper import rankings_to_schema
from kayfabe.app.dtos.ple_events_dto import MyselfQuery, MyselfResponse, MyselfUseCase
from kayfabe.app.exceptions import PleAuthRequiredError
from kayfabe.app.ports.input.ple_events_use_case import PleEventsUseCase
from kayfabe.app.ports.input.ple_match_pick_use_case import PleMatchPickUseCase
from kayfabe.dependencies.ple_events_provider import (
    get_ple_events,
)
from kayfabe.dependencies.ple_match_pick_provider import get_ple_match_pick

logger = logging.getLogger("uvicorn.error")

ple_match_pick_router = APIRouter(prefix="/ple-match-picks", tags=["ple-match-picks"])


def _ple_http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, LookupError):
        return HTTPException(status_code=404, detail=str(exc) or "Not found")
    if isinstance(exc, PleAuthRequiredError):
        return HTTPException(status_code=401, detail=str(exc) or "로그인이 필요합니다.")
    if isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=str(exc) or "잘못된 요청입니다.")
    raise exc


@ple_match_pick_router.get("/myself", response_model=None)
async def introduce_ranking_myself(
    use_case: MyselfUseCase = Depends(get_ple_match_pick),
) -> MyselfResponse:
    schema = MyselfSchema(id=4, name="ple_match_pick_router")
    query = MyselfQuery(id=schema.id, name=schema.name)
    return await use_case.introduce_myself(query)


@ple_match_pick_router.get(
    "/",
    response_model=RankingsResponseSchema,
    response_model_by_alias=True,
)
async def list_rankings(
    limit: int = 120,
    nickname: str | None = None,
    use_case: PleMatchPickUseCase = Depends(get_ple_match_pick),
):
    logger.info(
        "[PleMatchPickRouter] list_rankings | limit=%d nickname=%s",
        limit,
        nickname or "-",
    )
    return rankings_to_schema(
        await use_case.list_rankings(limit=limit, nickname=nickname)
    )


@ple_match_pick_router.post("/link-predictions", response_model_by_alias=True)
async def link_ple_predictions(body: LinkPredictionsSchema):
    raise HTTPException(
        status_code=410,
        detail="예측은 로그인 후 저장됩니다. link-predictions API는 더 이상 사용하지 않습니다.",
    )


@ple_match_pick_router.post(
    "/{slug}/predictions/batch",
    response_model=PleBoardSchema,
    response_model_by_alias=True,
)
async def predict_ple_batch(
    slug: str,
    body: BatchPredictionRequestSchema,
    use_case: PleEventsUseCase = Depends(get_ple_events),
):
    logger.info(
        "[PleMatchPickRouter] predict_ple_batch | slug=%s count=%d",
        slug,
        len(body.predictions),
    )
    try:
        board = await use_case.record_predictions_batch(
            slug=slug,
            body=batch_prediction_from_schema(body),
        )
        return board_to_schema(board)
    except (LookupError, ValueError, PleAuthRequiredError) as e:
        raise _ple_http_error(e) from e


@ple_match_pick_router.post(
    "/{slug}/matches/{match_key}/predict",
    response_model=PleBoardSchema,
    response_model_by_alias=True,
)
async def predict_ple_match(
    slug: str,
    match_key: str,
    body: PredictionRequestSchema,
    use_case: PleEventsUseCase = Depends(get_ple_events),
):
    logger.info(
        "[PleMatchPickRouter] predict_ple_match | slug=%s match=%s", slug, match_key
    )
    try:
        board = await use_case.record_prediction(
            slug=slug,
            match_key=match_key,
            body=prediction_from_schema(body),
        )
        return board_to_schema(board)
    except (LookupError, ValueError, PleAuthRequiredError) as e:
        raise _ple_http_error(e) from e
