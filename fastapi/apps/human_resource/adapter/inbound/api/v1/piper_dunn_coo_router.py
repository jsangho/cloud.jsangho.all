from fastapi import APIRouter, Depends
from human_resource.adapter.inbound.api.schemas.piper_dunn_coo_schema import (
    DunnCooSchema,
)
from human_resource.app.dtos.piper_dunn_coo_dto import DunnCooQuery, DunnCooResponse
from human_resource.app.ports.input.piper_dunn_coo_use_case import DunnCooUseCase
from human_resource.dependencies.piper_dunn_coo_provider import get_dunn_coo

"""
재러드 던 (Jared Dunn)
Pied Piper COO. 본명은 도널드 던. Richard의 충직한 조력자. Hooli 출신
"""
dunn_coo_router = APIRouter(prefix="/dunn", tags=["dunn"])


@dunn_coo_router.get("/myself")
async def introduce_myself(
    dunn: DunnCooUseCase = Depends(get_dunn_coo),
) -> DunnCooResponse:
    schema = DunnCooSchema(
        id=4,
        name="Jared Dunn",
    )
    query = DunnCooQuery(id=schema.id, name=schema.name)
    return await dunn.introduce_myself(query)
