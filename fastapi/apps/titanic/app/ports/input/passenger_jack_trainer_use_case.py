from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from titanic.app.dtos.passenger_jack_trainer_dto import (
    JackTrainerQuery,
    JackTrainerResponse,
)


class JackTrainerUseCase(ABC):
    """`/titanic/jack/*` inbound(jack_trainer_router) 입력 포트."""

    @abstractmethod
    async def introduce_myself(self, query: JackTrainerQuery) -> JackTrainerResponse:
        """잭 도슨 트레이너의 자기소개 메소드 (`GET /myself`)."""
        ...

    @abstractmethod
    async def train_model(self, train_set) -> dict[str, Any]:
        """로즈가 제안한 모델들을 훈련시키는 메소드."""
        ...
