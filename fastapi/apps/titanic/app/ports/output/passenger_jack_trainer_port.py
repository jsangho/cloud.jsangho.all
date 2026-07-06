from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from titanic.app.dtos.passenger_jack_trainer_dto import (
    JackTrainerQuery,
    JackTrainerResponse,
)


class JackTrainerPort(ABC):
    @abstractmethod
    async def introduce_myself(self, query: JackTrainerQuery) -> JackTrainerResponse:
        pass

    @abstractmethod
    async def get_training_data(self) -> list[dict[str, Any]]:
        """생존 예측 모델 학습에 사용할 피처 데이터 조회

        반환 키: pclass, gender, age, sibsp, parch, fare, survived
        """
        pass
