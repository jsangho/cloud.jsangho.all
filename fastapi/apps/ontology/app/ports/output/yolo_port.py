from __future__ import annotations

from abc import ABC, abstractmethod

from ontology.app.dtos.face_recognition_dto import (
    FaceRecognitionResult,
    FaceTrainConfig,
    FaceTrainResult,
)


class YoloPort(ABC):
    """YOLO(ultralytics) 모델 학습·추론을 수행하는 아웃바운드 포트.

    App 레이어는 이 포트만 바라보고, 어떤 YOLO 버전·가중치를 쓰는지는
    Outbound resource adapter(예: YoloResourceAdapter)가 책임진다.
    """

    @abstractmethod
    def train(self, dataset_root: str, config: FaceTrainConfig) -> FaceTrainResult:
        """dataset_root(train/val 클래스별 서브폴더)로 모델을 파인튜닝한다."""
        ...

    @abstractmethod
    def recognize(
        self, image_path: str, weights_path: str | None = None
    ) -> FaceRecognitionResult:
        """이미지 속 얼굴이 어떤 인물인지 예측한다."""
        ...
