from __future__ import annotations

from abc import ABC, abstractmethod

from vision.app.dtos.face_detection_dto import FaceDetectionResult


class FaceDetectorUseCase(ABC):
    """이미지 속 얼굴 위치(bounding box)를 찾는 유스케이스."""

    @abstractmethod
    def detect(self, image_path: str) -> FaceDetectionResult: ...
