from __future__ import annotations

from abc import ABC, abstractmethod

from ontology.app.dtos.face_identification_dto import FaceIdentificationResult


class FaceIdentificationUseCase(ABC):
    """탐지(위치) → 크롭 → 분류(인물)로 이어지는 얼굴 식별 파이프라인."""

    @abstractmethod
    def identify(
        self, image_path: str, classifier_weights_path: str | None = None
    ) -> FaceIdentificationResult:
        """이미지 속 각 얼굴의 위치와 인물을 함께 반환한다."""
        ...
