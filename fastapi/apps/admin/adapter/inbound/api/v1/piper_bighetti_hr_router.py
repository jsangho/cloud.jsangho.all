from admin.adapter.inbound.api.schemas.piper_bighetti_hr_schema import (
    BighettiHrSchema,
)
from admin.app.dtos.piper_bighetti_hr_dto import (
    BighettiHrQuery,
    BighettiHrResponse,
)
from admin.app.ports.input.piper_bighetti_hr_use_case import BighettiHrUseCase
from admin.dependencies.piper_bighetti_hr_provider import get_bighetti_hr

from fastapi import APIRouter, Depends

"""
넬슨 빅헤드 비게티 (Nelson Bighetti)
Pied Piper HR. 빅헤드라는 별명으로 불림. 우연한 행운으로 스탠퍼드 AI Lab 공동소장이 됨
"""
bighetti_hr_router = APIRouter(prefix="/bighetti", tags=["bighetti"])


@bighetti_hr_router.get("/myself")
async def introduce_myself(
    bighetti: BighettiHrUseCase = Depends(get_bighetti_hr),
) -> BighettiHrResponse:
    schema = BighettiHrSchema(
        id=2,
        name="Nelson Bighetti",
    )
    query = BighettiHrQuery(id=schema.id, name=schema.name)
    return await bighetti.introduce_myself(query)
