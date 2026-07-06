from fastapi import APIRouter, Depends
from human_resource.adapter.inbound.api.schemas.piper_gilfoyle_sys_schema import (
    GilfoyleSysSchema,
)
from human_resource.app.dtos.piper_gilfoyle_sys_dto import (
    GilfoyleSysQuery,
    GilfoyleSysResponse,
)
from human_resource.app.ports.input.piper_gilfoyle_sys_use_case import (
    GilfoyleSysUseCase,
)
from human_resource.dependencies.piper_gilfoyle_sys_provider import get_gilfoyle_sys

"""
버트램 길포일 (Bertram Gilfoyle)
Pied Piper 시스템 엔지니어. 냉소적 천재. 사탄교 신자. Dinesh와 항상 충돌
"""
gilfoyle_sys_router = APIRouter(prefix="/gilfoyle", tags=["gilfoyle"])


@gilfoyle_sys_router.get("/myself")
async def introduce_myself(
    gilfoyle: GilfoyleSysUseCase = Depends(get_gilfoyle_sys),
) -> GilfoyleSysResponse:
    schema = GilfoyleSysSchema(
        id=5,
        name="Bertram Gilfoyle",
    )
    query = GilfoyleSysQuery(id=schema.id, name=schema.name)
    return await gilfoyle.introduce_myself(query)
