from dataclasses import dataclass

from ontology.app.dtos.face_detection_dto import FaceBoundingBox
from ontology.app.dtos.face_recognition_dto import FacePrediction


@dataclass
class FaceIdentification:
    box: FaceBoundingBox
    predictions: list[FacePrediction]


@dataclass
class FaceIdentificationResult:
    image_path: str
    identifications: list[FaceIdentification]
