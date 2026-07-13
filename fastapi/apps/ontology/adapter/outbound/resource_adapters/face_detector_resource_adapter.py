from __future__ import annotations

from pathlib import Path

from ultralytics import YOLO
from ontology.app.dtos.face_detection_dto import FaceBoundingBox, FaceDetectionResult
from ontology.app.ports.output.face_detector_port import FaceDetectorPort

# 이미 학습 완료된 얼굴 탐지 전용 가중치 (task=detect, class: face)
_DEFAULT_WEIGHTS = str(
    Path(__file__).resolve().parents[3] / "resources" / "models" / "model.pt"
)


class FaceDetectorResourceAdapter(FaceDetectorPort):
    """ultralytics YOLO 얼굴 탐지 가중치를 실제로 호출하는 Outbound resource adapter."""

    def __init__(self, weights_path: str = _DEFAULT_WEIGHTS) -> None:
        self._weights_path = weights_path

    def detect(
        self, image_path: str, weights_path: str | None = None
    ) -> FaceDetectionResult:
        model = YOLO(weights_path or self._weights_path)
        result = model(image_path)[0]
        boxes = [
            FaceBoundingBox(
                x1=float(box.xyxy[0][0]),
                y1=float(box.xyxy[0][1]),
                x2=float(box.xyxy[0][2]),
                y2=float(box.xyxy[0][3]),
                confidence=float(box.conf[0]),
            )
            for box in result.boxes
        ]
        return FaceDetectionResult(image_path=image_path, boxes=boxes)
