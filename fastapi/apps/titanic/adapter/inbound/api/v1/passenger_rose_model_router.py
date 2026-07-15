from fastapi import APIRouter, Depends
from titanic.adapter.inbound.api.schemas.passenger_rose_model_schema import (
    RoseModelSchema,
)
from titanic.app.dtos.passenger_rose_model_dto import RoseModelQuery, RoseModelResponse
from titanic.app.ports.input.passenger_rose_model_use_case import RoseModelUseCase
from titanic.dependencies.passenger_rose_model_provider import get_rose_model

"""
로즈 드윗 부카터 (Rose DeWitt Bukater)
ML 모델 결과 분석·조회 담당자
"""
rose_model_router = APIRouter(prefix="/rose", tags=["rose"])


@rose_model_router.get("/myself")
async def introduce_myself(
    rose: RoseModelUseCase = Depends(get_rose_model),
) -> RoseModelResponse:
    schema = RoseModelSchema(
        id=11,
        name="Rose DeWitt Bukater",
        memo="상류층의 답답함에서 벗어나고자 하는 의지. ML 모델 결과 분석·조회 담당자",
    )
    query = RoseModelQuery(id=schema.id, name=schema.name)
    return await rose.introduce_myself(query)
