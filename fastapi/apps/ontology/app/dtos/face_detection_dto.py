from dataclasses import dataclass


@dataclass
class FaceBoundingBox:
    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float


@dataclass
class FaceDetectionResult:
    image_path: str
    boxes: list[FaceBoundingBox]
