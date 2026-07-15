from fastapi import APIRouter, Depends
from titanic.adapter.inbound.api.schemas.crew_walter_roaster_schema import (
    WalterRoasterOpenfileResponse,
    WalterRoasterPassengerItem,
    WalterRoasterSchema,
)
from titanic.app.dtos.crew_walter_roaster_dto import (
    WalterRoasterQuery,
    WalterRoasterResponse,
)
from titanic.app.ports.input.crew_walter_roaster_use_case import WalterRoasterUseCase
from titanic.dependencies.crew_walter_roaster_provider import get_walter_roaster

"""
윌터 와일딩 (Walter Nichols)
영화 <타이타닉>에서 승객 명단을 관리하는
일등 항해사. 승객 명단 관리 담당자
"""
walter_roaster_router = APIRouter(prefix="/walter", tags=["walter"])

_DEFAULT_WALTER = {
    "id": 2,
    "name": "Walter Nichols",
    "memo": "타이타닉의 일등 항해사, 승객 명단 관리 담당",
}


@walter_roaster_router.get("/myself")
async def introduce_myself(
    walter: WalterRoasterUseCase = Depends(get_walter_roaster),
) -> WalterRoasterResponse:
    schema = WalterRoasterSchema(
        id=6,
        name="Walter Nichols",
        memo="타이타닉의 일등 항해사, 승객 명단 관리 담당",
    )
    query = WalterRoasterQuery(id=schema.id, name=schema.name)
    return await walter.introduce_myself(query)


@walter_roaster_router.get("/openfile", response_model=WalterRoasterOpenfileResponse)
async def openfile(
    page: int = 1,
    pageSize: int = 50,
    walter: WalterRoasterUseCase = Depends(get_walter_roaster),
) -> WalterRoasterOpenfileResponse:
    page_result = await walter.list_openfile_page(page=page, page_size=pageSize)
    return WalterRoasterOpenfileResponse(
        id=_DEFAULT_WALTER["id"],
        name=_DEFAULT_WALTER["name"],
        memo=_DEFAULT_WALTER["memo"],
        page=page_result["page"],
        pageSize=page_result["pageSize"],
        total=page_result["total"],
        items=[
            WalterRoasterPassengerItem.model_validate(item)
            for item in page_result["items"]
        ],
    )
