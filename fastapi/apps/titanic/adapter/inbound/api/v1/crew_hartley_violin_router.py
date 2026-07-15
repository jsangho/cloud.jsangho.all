import io

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from titanic.adapter.inbound.api.schemas.crew_hartley_violin_schema import (
    HartleyViolinSchema,
)
from titanic.app.dtos.crew_hartley_violin_dto import (
    HartleyViolinQuery,
    HartleyViolinResponse,
)
from titanic.app.ports.input.crew_hartley_violin_use_case import HartleyViolinUseCase
from titanic.app.ports.input.crew_walter_roaster_use_case import WalterRoasterUseCase
from titanic.dependencies.crew_hartley_violin_provider import get_hartley_violin
from titanic.dependencies.crew_walter_roaster_provider import get_walter_roaster

"""
왈리스 하틀리 (Wallace Hartley - 악단장)
배가 가라앉는 극도의 공포 속에서도 승객들을 진정시키기 위해 끝까지 찬송가를 연주했던 악단장입니다.
"""
hartley_violin_router = APIRouter(prefix="/hartley", tags=["hartley"])


@hartley_violin_router.get("/myself")
async def introduce_myself(
    hartley: HartleyViolinUseCase = Depends(get_hartley_violin),
) -> HartleyViolinResponse:
    schema = HartleyViolinSchema(
        id=3,
        name="Wallace Hartley",
        memo="배가 가라앉는 극도의 공포 속에서도 승객들을 진정시키기 위해 끝까지 찬송가를 연주했던 악단장입니다.",
    )
    query = HartleyViolinQuery(id=schema.id, name=schema.name)
    return await hartley.introduce_myself(query)


@hartley_violin_router.get("/correlation", response_class=StreamingResponse)
async def get_correlation_heatmap(
    hartley: HartleyViolinUseCase = Depends(get_hartley_violin),
    walter: WalterRoasterUseCase = Depends(get_walter_roaster),
) -> StreamingResponse:
    df = await walter.get_train_set()
    image_bytes = hartley.get_correlation_heatmap(df)
    return StreamingResponse(io.BytesIO(image_bytes), media_type="image/png")


@hartley_violin_router.get("/survival", response_class=StreamingResponse)
async def get_survival_rate_chart(
    hartley: HartleyViolinUseCase = Depends(get_hartley_violin),
    walter: WalterRoasterUseCase = Depends(get_walter_roaster),
) -> StreamingResponse:
    df = await walter.get_train_set()
    image_bytes = hartley.get_survival_rate_chart(df)
    return StreamingResponse(io.BytesIO(image_bytes), media_type="image/png")
