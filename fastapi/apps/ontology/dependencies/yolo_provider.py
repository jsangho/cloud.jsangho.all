from ontology.adapter.outbound.repositories.local_yolo_face_dataset_repository import (
    LocalYoloFaceDatasetRepository,
)
from ontology.adapter.outbound.resource_adapters.yolo_resource_adapter import (
    YoloResourceAdapter,
)
from ontology.app.ports.input.face_recognizer_use_case import FaceRecognizerUseCase
from ontology.app.use_cases.yolo_interactor import YoloInteractor


def get_yolo_use_case() -> FaceRecognizerUseCase:
    return YoloInteractor(
        dataset_repository=LocalYoloFaceDatasetRepository(),
        yolo_port=YoloResourceAdapter(),
    )
