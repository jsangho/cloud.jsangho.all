from __future__ import annotations

from abc import ABC, abstractmethod

from titanic.app.dtos.passenger_rose_model_dto import (
    PassengerFeaturesQuery,
    RoseModelQuery,
    RoseModelResponse,
    SurvivalPredictionResponse,
)


class SurvivalPredictionStrategy(ABC):
    """생존 예측 알고리즘 전략 인터페이스 (Strategy)."""

    @property
    @abstractmethod
    def algorithm_name(self) -> str: ...

    @abstractmethod
    def fit(self, X: list[list[float]], y: list[int]) -> None:
        """학습 데이터로 모델 피팅."""
        ...

    @abstractmethod
    def predict(self, features: PassengerFeaturesQuery) -> SurvivalPredictionResponse:
        """승객 피처로 생존 예측 (단건)."""
        ...

    @abstractmethod
    def batch_predict(self, X: list[list[float]]) -> list[int]:
        """여러 샘플에 대한 배치 예측 (0=사망, 1=생존)."""
        ...


class RoseModelUseCase(ABC):
    """`/titanic/rose/*` inbound(rose_model_router) 입력 포트."""

    @abstractmethod
    async def introduce_myself(self, query: RoseModelQuery) -> RoseModelResponse:
        """로즈 드윗 부카터의 자기소개 메소드 (`GET /myself`)."""
        ...

    @abstractmethod
    def list_algorithms(self) -> list[str]:
        """사용 가능한 알고리즘 키 목록 반환."""
        ...

    @abstractmethod
    async def train(self, X: list[list[float]], y: list[int], algorithm: str) -> None:
        """선택한 알고리즘 전략을 학습 데이터로 피팅 (`POST /train`)."""
        ...

    @abstractmethod
    async def predict(
        self, features: PassengerFeaturesQuery, algorithm: str
    ) -> SurvivalPredictionResponse:
        """지정 알고리즘으로 생존 여부 예측 (`POST /predict`)."""
        ...

    @abstractmethod
    async def batch_predict(self, X: list[list[float]], algorithm: str) -> list[int]:
        """지정 알고리즘으로 배치 예측 (`POST /batch-predict`)."""
        ...
