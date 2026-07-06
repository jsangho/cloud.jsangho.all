from typing import Any

from fastapi import APIRouter, Depends
from titanic.adapter.inbound.api.schemas.passenger_jack_trainer_schema import (
    JackTrainerSchema,
)
from titanic.app.dtos.passenger_jack_trainer_dto import (
    JackTrainerQuery,
    JackTrainerResponse,
)
from titanic.app.ports.input.crew_walter_roaster_use_case import WalterRoasterUseCase
from titanic.app.ports.input.passenger_jack_trainer_use_case import JackTrainerUseCase
from titanic.dependencies.crew_walter_roaster_provider import get_walter_roaster
from titanic.dependencies.passenger_jack_trainer_provider import get_jack_trainer

"""
잭 도슨 (Jack Dawson)
생존 예측 모델의 핵심 인터페이스를 담당합니다.
"""
jack_trainer_router = APIRouter(prefix="/jack", tags=["jack"])


@jack_trainer_router.post("/train")
async def train_model(
    jack: JackTrainerUseCase = Depends(get_jack_trainer),
    walter: WalterRoasterUseCase = Depends(get_walter_roaster),
) -> dict[str, Any]:
    train_set = await walter.get_train_set()
    result = await jack.train_model(train_set)
    return {
        "train_samples": result["train_samples"],
        "trained_models": result["trained_models"],
    }


@jack_trainer_router.get("/myself")
async def introduce_myself(
    jack: JackTrainerUseCase = Depends(get_jack_trainer),
) -> JackTrainerResponse:
    schema = JackTrainerSchema(
        id=9,
        name="Jack Dawson",
        memo="자유로운 영혼의 3등석 화가. 로즈에게 진정한 삶을 가르쳐준 인물이자 타이타닉 생존 스토리의 주역",
    )
    query = JackTrainerQuery(id=schema.id, name=schema.name)
    return await jack.introduce_myself(query)
