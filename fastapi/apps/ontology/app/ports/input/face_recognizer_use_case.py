from __future__ import annotations

from abc import ABC, abstractmethod

from ontology.app.dtos.face_recognition_dto import (
    FaceRecognitionResult,
    FaceTrainConfig,
    FaceTrainResult,
)


class FaceRecognizerUseCase(ABC):
    """얼굴 인식(분류) 파인튜닝 · 추론 유스케이스."""

    @abstractmethod
    def train(self, config: FaceTrainConfig) -> FaceTrainResult:
        """데이터셋으로 YOLO 분류 모델을 파인튜닝한다."""
        ...

    @abstractmethod
    def recognize(
        self, image_path: str, weights_path: str | None = None
    ) -> FaceRecognitionResult:
        """이미지 속 얼굴이 어떤 인물인지 예측한다."""
        ...
