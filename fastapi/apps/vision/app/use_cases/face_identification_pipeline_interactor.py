from __future__ import annotations

import os
import tempfile

from PIL import Image
from vision.app.dtos.face_identification_dto import (
    FaceIdentification,
    FaceIdentificationResult,
)
from vision.app.ports.input.face_identification_use_case import (
    FaceIdentificationUseCase,
)
from vision.app.ports.output.face_detector_port import FaceDetectorPort
from vision.app.ports.output.yolo_port import YoloPort


class FaceIdentificationPipelineInteractor(FaceIdentificationUseCase):
    """FaceDetectorPort(탐지)와 YoloPort(분류)를 엮는 오케스트레이터."""

    def __init__(
        self, face_detector_port: FaceDetectorPort, yolo_port: YoloPort
    ) -> None:
        self._face_detector_port = face_detector_port
        self._yolo_port = yolo_port

    def identify(
        self, image_path: str, classifier_weights_path: str | None = None
    ) -> FaceIdentificationResult:
        detection = self._face_detector_port.detect(image_path)

        identifications = []
        with Image.open(image_path) as image:
            for box in detection.boxes:
                crop = image.convert("RGB").crop((box.x1, box.y1, box.x2, box.y2))
                fd, crop_path = tempfile.mkstemp(suffix=".jpg")
                try:
                    os.close(fd)
                    crop.save(crop_path)
                    recognition = self._yolo_port.recognize(
                        crop_path, classifier_weights_path
                    )
                finally:
                    os.remove(crop_path)

                identifications.append(
                    FaceIdentification(box=box, predictions=recognition.predictions)
                )

        return FaceIdentificationResult(
            image_path=image_path, identifications=identifications
        )
