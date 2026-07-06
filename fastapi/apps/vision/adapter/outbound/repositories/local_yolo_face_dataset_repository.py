from __future__ import annotations

from pathlib import Path

from vision.app.ports.output.face_dataset_repository import FaceDatasetRepository

_DEFAULT_DATASET_ROOT = Path(__file__).resolve().parents[3] / "resources" / "yolo_train"


class LocalYoloFaceDatasetRepository(FaceDatasetRepository):
    """로컬 디렉터리(resources/yolo_train)에서 얼굴 인식 데이터셋을 연결하는 어댑터."""

    def __init__(self, dataset_root: str | Path = _DEFAULT_DATASET_ROOT) -> None:
        self._dataset_root = Path(dataset_root)

    def get_dataset_root(self) -> str:
        train_dir = self._dataset_root / "train"
        val_dir = self._dataset_root / "val"
        if not train_dir.is_dir() or not val_dir.is_dir():
            raise FileNotFoundError(
                f"YOLO 분류 데이터셋 train/val 폴더를 찾을 수 없음: {self._dataset_root}"
            )
        return str(self._dataset_root)
