from fastapi import APIRouter, Depends
from admin.adapter.inbound.api.schemas.piper_hendricks_ceo_schema import (
    HendricksCeoSchema,
)
from admin.app.dtos.piper_hendricks_ceo_dto import (
    HendricksCeoQuery,
    HendricksCeoResponse,
)
from admin.app.ports.input.piper_hendricks_ceo_use_case import (
    HendricksCeoUseCase,
)
from admin.dependencies.piper_hendricks_ceo_provider import get_hendricks_ceo

"""
리처드 헨드릭스 (Richard Hendricks)
Pied Piper CEO. 미들아웃 압축 알고리즘 발명자
"""
hendricks_ceo_router = APIRouter(prefix="/hendricks", tags=["hendricks"])


@hendricks_ceo_router.get("/myself")
async def introduce_myself(
    hendricks: HendricksCeoUseCase = Depends(get_hendricks_ceo),
) -> HendricksCeoResponse:
    schema = HendricksCeoSchema(
        id=1,
        name="Richard Hendricks",
    )
    query = HendricksCeoQuery(id=schema.id, name=schema.name)
    return await hendricks.introduce_myself(query)
