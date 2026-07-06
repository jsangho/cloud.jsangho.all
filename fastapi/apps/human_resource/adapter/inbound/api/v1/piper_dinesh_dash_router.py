from fastapi import APIRouter, Depends
from human_resource.adapter.inbound.api.schemas.piper_dinesh_dash_schema import (
    DineshDashSchema,
)
from human_resource.app.dtos.piper_dinesh_dash_dto import (
    DineshDashQuery,
    DineshDashResponse,
)
from human_resource.app.ports.input.piper_dinesh_dash_use_case import DineshDashUseCase
from human_resource.dependencies.piper_dinesh_dash_provider import get_dinesh_dash

"""
디네시 추타이 (Dinesh Chugtai)
Pied Piper 대시보드 엔지니어. 자칭 "웹소켓 전문가". 길포일과 항상 티격태격
"""
dinesh_dash_router = APIRouter(prefix="/dinesh", tags=["dinesh"])


@dinesh_dash_router.get("/myself")
async def introduce_myself(
    dinesh: DineshDashUseCase = Depends(get_dinesh_dash),
) -> DineshDashResponse:
    schema = DineshDashSchema(
        id=3,
        name="Dinesh Chugtai",
    )
    query = DineshDashQuery(id=schema.id, name=schema.name)
    return await dinesh.introduce_myself(query)
