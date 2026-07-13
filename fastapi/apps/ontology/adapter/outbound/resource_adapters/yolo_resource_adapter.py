from __future__ import annotations

from pathlib import Path

from ultralytics import YOLO

from ontology.app.dtos.face_recognition_dto import (
    FacePrediction,
    FaceRecognitionResult,
    FaceTrainConfig,
    FaceTrainResult,
)
from ontology.app.ports.output.yolo_port import YoloPort

# YOLOv11 Nano(classify) — 가장 가벼운 환경에서 빠르게 파인튜닝·검증하기 위한 초경량 백본
_DEFAULT_PRETRAINED_WEIGHTS = "yolo11n-cls.pt"


class YoloResourceAdapter(YoloPort):
    """ultralytics YOLO를 실제로 호출하는 Outbound resource adapter."""

    def __init__(self, pretrained_weights: str = _DEFAULT_PRETRAINED_WEIGHTS) -> None:
        self._pretrained_weights = pretrained_weights

    def train(self, dataset_root: str, config: FaceTrainConfig) -> FaceTrainResult:
        model = YOLO(self._pretrained_weights)
        results = model.train(
            data=dataset_root,
            epochs=config.epochs,
            imgsz=config.image_size,
            batch=config.batch_size,
            device=config.device,
        )
        best_weights = Path(results.save_dir) / "weights" / "best.pt"
        return FaceTrainResult(
            best_weights_path=str(best_weights),
            save_dir=str(results.save_dir),
        )

    def recognize(
        self, image_path: str, weights_path: str | None = None
    ) -> FaceRecognitionResult:
        model = YOLO(weights_path or self._pretrained_weights)
        result = model(image_path)[0]
        names = result.names
        predictions = [
            FacePrediction(name=names[i], confidence=float(result.probs.data[i]))
            for i in result.probs.top5
        ]
        return FaceRecognitionResult(image_path=image_path, predictions=predictions)
