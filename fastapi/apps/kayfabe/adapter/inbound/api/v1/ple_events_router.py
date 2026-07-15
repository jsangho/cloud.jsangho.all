from __future__ import annotations

import asyncio
import json
import logging

from core.matrix.grid_oracle_database_manager import (
    AsyncSessionLocal,
    rollback_readonly,
)
from fastapi.responses import StreamingResponse

from fastapi import APIRouter, Depends, HTTPException, Request
from kayfabe.adapter.inbound.api.schemas.ple_events_schema import (
    MyselfSchema,
    PleAiStatsSchema,
    PleBoardSchema,
    PleEventSummarySchema,
    PleEventSyncSchema,
    PleResultsResponseSchema,
)
from kayfabe.adapter.outbound.mappers.ple_schema_mapper import (
    ai_stats_to_schema,
    board_to_schema,
    event_summary_to_schema,
    event_sync_from_schema,
)
from kayfabe.app.dtos.ple_events_dto import MyselfQuery, MyselfResponse, MyselfUseCase
from kayfabe.app.exceptions import PleAuthRequiredError
from kayfabe.app.ports.input.ple_events_use_case import PleEventsUseCase
from kayfabe.dependencies.ple_events_provider import (
    get_ple_events,
    get_ple_events_repository,
)

logger = logging.getLogger("uvicorn.error")

ple_events_router = APIRouter(prefix="/ple_events", tags=["ple-events"])


def _ple_http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, LookupError):
        return HTTPException(status_code=404, detail=str(exc) or "Not found")
    if isinstance(exc, PleAuthRequiredError):
        return HTTPException(status_code=401, detail=str(exc) or "로그인이 필요합니다.")
    if isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=str(exc) or "잘못된 요청입니다.")
    raise exc


@ple_events_router.get("/myself", response_model=None)
async def introduce_ple_events_myself(
    use_case: MyselfUseCase = Depends(get_ple_events),
) -> MyselfResponse:
    schema = MyselfSchema(id=2, name="ple_events_router")
    query = MyselfQuery(id=schema.id, name=schema.name)
    return await use_case.introduce_myself(query)


@ple_events_router.get(
    "/events",
    response_model=list[PleEventSummarySchema],
    response_model_by_alias=True,
)
async def list_ple_events(use_case: PleEventsUseCase = Depends(get_ple_events)):
    logger.info("[PleEventsRouter] list_ple_events")
    events = await use_case.list_events()
    return [event_summary_to_schema(e) for e in events]


@ple_events_router.get(
    "/ai-stats",
    response_model=PleAiStatsSchema,
    response_model_by_alias=True,
)
async def get_ple_ai_stats(use_case: PleEventsUseCase = Depends(get_ple_events)):
    logger.info("[PleEventsRouter] get_ple_ai_stats")
    return ai_stats_to_schema(await use_case.get_ai_stats())


@ple_events_router.get("/results", response_model=PleResultsResponseSchema)
async def list_ple_results(
    year: int = 2026,
    use_case: PleEventsUseCase = Depends(get_ple_events),
):
    return (await use_case.list_results(year)).to_schema()


@ple_events_router.post(
    "/{slug}/sync-from-client",
    response_model=PleBoardSchema,
    response_model_by_alias=True,
)
async def sync_ple_from_client(
    slug: str,
    payload: PleEventSyncSchema,
    use_case: PleEventsUseCase = Depends(get_ple_events),
):
    if payload.slug != slug:
        raise HTTPException(
            status_code=400, detail="URL slug와 본문 slug가 일치하지 않습니다."
        )
    logger.info(
        "[PleEventsRouter] sync_ple_from_client | slug=%s matches=%d",
        slug,
        len(payload.matches),
    )
    try:
        board = await use_case.sync_event(payload=event_sync_from_schema(payload))
        return board_to_schema(board)
    except ValueError as e:
        raise _ple_http_error(e) from e


@ple_events_router.get(
    "/{slug}",
    response_model=PleBoardSchema,
    response_model_by_alias=True,
)
async def get_ple_board(
    slug: str,
    client_id: str | None = None,
    user_id: int | None = None,
    use_case: PleEventsUseCase = Depends(get_ple_events),
):
    logger.info("[PleEventsRouter] get_ple_board | slug=%s", slug)
    try:
        return board_to_schema(
            await use_case.get_board(slug=slug, client_id=client_id, user_id=user_id)
        )
    except LookupError as e:
        raise _ple_http_error(e) from e


@ple_events_router.get("/{slug}/live")
async def ple_live_board(
    slug: str,
    client_id: str,
    request: Request,
    user_id: int | None = None,
):
    async def event_stream():
        if AsyncSessionLocal is None:
            yield f"data: {json.dumps({'error': 'DATABASE_URL not configured'})}\n\n"
            return
        try:
            while True:
                if await request.is_disconnected():
                    return
                try:
                    async with AsyncSessionLocal() as session:
                        use_case = get_ple_events(get_ple_events_repository(session))
                        board = await use_case.get_board(
                            slug=slug, client_id=client_id, user_id=user_id
                        )
                        await rollback_readonly(session)
                except LookupError as e:
                    yield f"data: {json.dumps({'error': str(e)})}\n\n"
                    return
                except asyncio.CancelledError:
                    return
                payload = board_to_schema(board).model_dump(mode="json", by_alias=True)
                yield f"data: {json.dumps(payload, default=str)}\n\n"
                try:
                    await asyncio.sleep(3)
                except asyncio.CancelledError:
                    return
        except asyncio.CancelledError:
            return

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
