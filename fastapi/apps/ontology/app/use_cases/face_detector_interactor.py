from __future__ import annotations

from ontology.app.dtos.face_detection_dto import FaceDetectionResult
from ontology.app.ports.input.face_detector_use_case import FaceDetectorUseCase
from ontology.app.ports.output.face_detector_port import FaceDetectorPort


class FaceDetectorInteractor(FaceDetectorUseCase):
    def __init__(self, face_detector_port: FaceDetectorPort) -> None:
        self._face_detector_port = face_detector_port

    def detect(self, image_path: str) -> FaceDetectionResult:
        return self._face_detector_port.detect(image_path)
