from dataclasses import dataclass


@dataclass(frozen=True)
class FaceTrainConfig:
    epochs: int = 50
    image_size: int = 224
    batch_size: int = 16
    device: str | None = None


@dataclass
class FaceTrainResult:
    best_weights_path: str
    save_dir: str


@dataclass
class FacePrediction:
    name: str
    confidence: float


@dataclass
class FaceRecognitionResult:
    image_path: str
    predictions: list[FacePrediction]
