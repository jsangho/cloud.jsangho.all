from __future__ import annotations

from vision.app.dtos.face_detection_dto import FaceDetectionResult
from vision.app.ports.input.face_detector_use_case import FaceDetectorUseCase
from vision.app.ports.output.face_detector_port import FaceDetectorPort


class FaceDetectorInteractor(FaceDetectorUseCase):
    def __init__(self, face_detector_port: FaceDetectorPort) -> None:
        self._face_detector_port = face_detector_port

    def detect(self, image_path: str) -> FaceDetectionResult:
        return self._face_detector_port.detect(image_path)
