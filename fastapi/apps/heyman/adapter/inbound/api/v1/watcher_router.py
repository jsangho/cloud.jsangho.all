from fastapi import APIRouter, Depends
from heyman.adapter.inbound.api.schemas.watcher_schema import (
    WatcherFilterRequest,
    WatcherFilterResponse,
    WatcherMyselfSchema,
)
from heyman.app.dtos.receiver_dto import ReceiverCommand
from heyman.app.dtos.watcher_dto import WatcherQuery, WatcherResponse
from heyman.app.ports.input.watcher_use_case import WatcherUseCase
from heyman.dependencies.watcher_provider import get_watcher_use_case

watcher_router = APIRouter(prefix="/watcher", tags=["watcher"])


@watcher_router.get("/myself")
async def introduce_myself(
    use_case: WatcherUseCase = Depends(get_watcher_use_case),
) -> WatcherResponse:
    schema = WatcherMyselfSchema()
    query = WatcherQuery(id=schema.id, name=schema.name)
    return await use_case.introduce_myself(query)


@watcher_router.post(
    "/filter", summary="KcELECTRA 1차 필터링 → 정상 메일만 pgvector 저장"
)
async def filter_mail(
    body: WatcherFilterRequest,
    use_case: WatcherUseCase = Depends(get_watcher_use_case),
) -> WatcherFilterResponse:
    cmd = ReceiverCommand(
        from_email=body.from_email,
        from_name=body.from_name,
        to_email=body.to_email,
        subject=body.subject,
        body=body.body,
        message_id=body.message_id,
    )
    result = await use_case.filter_and_forward(cmd)
    return WatcherFilterResponse(
        id=result.id,
        label=result.label,
        confidence=result.confidence,
        forwarded=result.forwarded,
    )
