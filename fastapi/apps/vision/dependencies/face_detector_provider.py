from vision.adapter.outbound.resource_adapters.face_detector_resource_adapter import (
    FaceDetectorResourceAdapter,
)
from vision.app.ports.input.face_detector_use_case import FaceDetectorUseCase
from vision.app.use_cases.face_detector_interactor import FaceDetectorInteractor


def get_face_detector_use_case() -> FaceDetectorUseCase:
    return FaceDetectorInteractor(face_detector_port=FaceDetectorResourceAdapter())
