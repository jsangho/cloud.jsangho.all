from fastapi import APIRouter, Depends
from titanic.adapter.inbound.api.schemas.passenger_cal_tester_schema import (
    CalTesterSchema,
)
from titanic.app.dtos.passenger_cal_tester_dto import CalTesterQuery, CalTesterResponse
from titanic.app.ports.input.passenger_cal_tester_use_case import CalTesterUseCase
from titanic.dependencies.passenger_cal_tester_provider import get_cal_tester

"""
칼 캘던 하클리 (Caledon Hockley)
승객 입력값 유효성 검사를 담당합니다.
"""
cal_tester_router = APIRouter(prefix="/cal", tags=["cal"])


@cal_tester_router.get("/myself")
async def introduce_myself(
    cal: CalTesterUseCase = Depends(get_cal_tester),
) -> CalTesterResponse:
    schema = CalTesterSchema(
        id=6,
        name="Caledon Hockley",
    )
    query = CalTesterQuery(id=schema.id, name=schema.name)
    return await cal.introduce_myself(query)
