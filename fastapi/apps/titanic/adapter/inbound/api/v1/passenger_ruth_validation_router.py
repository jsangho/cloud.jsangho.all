from fastapi import APIRouter, Depends
from titanic.adapter.inbound.api.schemas.passenger_ruth_validation_schema import (
    RuthValidationSchema,
)
from titanic.app.dtos.passenger_ruth_validation_dto import (
    RuthValidationQuery,
    RuthValidationResponse,
)
from titanic.app.ports.input.passenger_ruth_validation_use_case import (
    RuthValidationUseCase,
)
from titanic.dependencies.passenger_ruth_validation_provider import get_ruth_validation

"""
루스 드윗 부카터 (Ruth DeWitt Bukater)
1등석 승객(상류층) 조회를 담당한다.
"""
ruth_validation_router = APIRouter(prefix="/ruth", tags=["ruth"])


@ruth_validation_router.get("/myself")
async def introduce_myself(
    ruth: RuthValidationUseCase = Depends(get_ruth_validation),
) -> RuthValidationResponse:
    schema = RuthValidationSchema(
        id=12,
        name="Ruth DeWitt Bukater",
        memo="딸 로즈의 코르셋 끈을 강하게 조이며 상류층의 체면을 강요하던 통제욕의 상징. 1등석 승객(상류층) 조회를 담당한다.",
    )
    query = RuthValidationQuery(id=schema.id, name=schema.name)
    return await ruth.introduce_myself(query)
