from __future__ import annotations

from abc import ABC, abstractmethod


class FaceDatasetRepository(ABC):
    """얼굴 인식 학습용 데이터셋(YOLO classify 포맷) 연결 포트."""

    @abstractmethod
    def get_dataset_root(self) -> str:
        """train/val 클래스별 서브폴더를 담은 데이터셋 루트 경로를 반환한다."""
        ...
