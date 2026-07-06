from __future__ import annotations

from vision.app.dtos.face_recognition_dto import (
    FaceRecognitionResult,
    FaceTrainConfig,
    FaceTrainResult,
)
from vision.app.ports.input.face_recognizer_use_case import FaceRecognizerUseCase
from vision.app.ports.output.face_dataset_repository import FaceDatasetRepository
from vision.app.ports.output.yolo_port import YoloPort


class YoloInteractor(FaceRecognizerUseCase):
    """데이터셋 위치도, YOLO 버전/가중치도 모르는 순수 오케스트레이터."""

    def __init__(
        self, dataset_repository: FaceDatasetRepository, yolo_port: YoloPort
    ) -> None:
        self._dataset_repository = dataset_repository
        self._yolo_port = yolo_port

    def train(self, config: FaceTrainConfig) -> FaceTrainResult:
        dataset_root = self._dataset_repository.get_dataset_root()
        return self._yolo_port.train(dataset_root, config)

    def recognize(
        self, image_path: str, weights_path: str | None = None
    ) -> FaceRecognitionResult:
        return self._yolo_port.recognize(image_path, weights_path)
