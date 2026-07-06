from pathlib import Path

from vision.adapter.outbound.resource_adapters.face_detector_resource_adapter import (
    FaceDetectorResourceAdapter,
)
from vision.adapter.outbound.resource_adapters.yolo_resource_adapter import (
    YoloResourceAdapter,
)
from vision.app.ports.input.face_identification_use_case import (
    FaceIdentificationUseCase,
)
from vision.app.use_cases.face_identification_pipeline_interactor import (
    FaceIdentificationPipelineInteractor,
)

# resources/yolo_train으로 파인튜닝한 인물 분류 가중치 (기본 yolo11n-cls.pt가 아님)
_FACE_CLASSIFIER_WEIGHTS = str(
    Path(__file__).resolve().parents[1] / "resources" / "models" / "face_classifier.pt"
)


def get_face_identification_use_case() -> FaceIdentificationUseCase:
    return FaceIdentificationPipelineInteractor(
        face_detector_port=FaceDetectorResourceAdapter(),
        yolo_port=YoloResourceAdapter(pretrained_weights=_FACE_CLASSIFIER_WEIGHTS),
    )
