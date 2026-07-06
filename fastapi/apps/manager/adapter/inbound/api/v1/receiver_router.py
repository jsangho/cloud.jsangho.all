from __future__ import annotations

from fastapi import APIRouter, Depends
from manager.adapter.inbound.api.schemas.receiver_schema import (
    ReceiverRequest,
    ReceiverResponse,
)
from manager.app.dtos.receiver_dto import ReceiverCommand
from manager.app.ports.input.receiver_use_case import ReceiverUseCase
from manager.dependencies.receiver_provider import get_receiver_use_case

receiver_router = APIRouter(prefix="/receiver", tags=["receiver"])


@receiver_router.post("/receive", summary="n8n → 수신 데이터 저장")
async def receiver(
    body: ReceiverRequest,
    use_case: ReceiverUseCase = Depends(get_receiver_use_case),
) -> dict[str, int | None]:
    cmd = ReceiverCommand(
        from_email=body.from_email,
        from_name=body.from_name,
        to_email=body.to_email,
        subject=body.subject,
        body=body.body,
        message_id=body.message_id,
    )
    return await use_case.receiver(cmd)


@receiver_router.get("/list", summary="받은편지함 목록 조회")
async def list_receiver(
    use_case: ReceiverUseCase = Depends(get_receiver_use_case),
) -> list[ReceiverResponse]:
    items = await use_case.list_receiver()
    return [
        ReceiverResponse(
            id=item.id,
            from_email=item.from_email,
            from_name=item.from_name,
            to_email=item.to_email,
            subject=item.subject,
            body=item.body,
            message_id=item.message_id,
            receiver_at=item.receiver_at,
            is_read=item.is_read,
            spam_label=item.spam_label,
            spam_confidence=item.spam_confidence,
        )
        for item in items
    ]


@receiver_router.patch("/{item_id}/read", summary="읽음 처리")
async def mark_read(
    item_id: int,
    use_case: ReceiverUseCase = Depends(get_receiver_use_case),
) -> dict[str, str]:
    await use_case.mark_read(item_id)
    return {"status": "ok"}
