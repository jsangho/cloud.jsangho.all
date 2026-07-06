from __future__ import annotations

from abc import ABC, abstractmethod

from vision.app.dtos.face_detection_dto import FaceDetectionResult


class FaceDetectorPort(ABC):
    """사전 학습된 얼굴 탐지 YOLO 모델을 호출하는 아웃바운드 포트."""

    @abstractmethod
    def detect(
        self, image_path: str, weights_path: str | None = None
    ) -> FaceDetectionResult:
        """이미지에서 얼굴 위치(bounding box)를 찾는다."""
        ...
