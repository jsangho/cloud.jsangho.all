from __future__ import annotations

import asyncio
import io
from typing import Any, ClassVar

import timm
import torch
from core.matrix.vault_keymaker_secret_manager import get_keymaker
from PIL import Image, UnidentifiedImageError
from timm.data import ImageNetInfo

from ontology.app.dtos.image_classification_dto import (
    ImageClassificationDto,
    TopKPredictionDto,
)
from ontology.app.ports.output.image_label_classifier import ImageLabelClassifier

_MODEL_NAME = "convnext_nano"
_TOP_K = 5


def _confidence_threshold() -> float:
    return float(get_keymaker().get_secret("CLASSIFIER_CONFIDENCE_THRESHOLD", "0.5"))


class ConvNextImageClassifier(ImageLabelClassifier):
    """timm `convnext_nano`(ImageNet-1k 사전학습) 기반 단일 라벨 이미지 분류 어댑터.

    모델·전처리 파이프라인은 프로세스에서 한 번만 로드해 재사용한다(클래스 변수 캐시).
    """

    _model: ClassVar[torch.nn.Module | None] = None
    _transform: ClassVar[Any] = None
    _labels: ClassVar[ImageNetInfo | None] = None
    _device: ClassVar[str] = "cuda" if torch.cuda.is_available() else "cpu"

    def _ensure_loaded(self) -> None:
        if ConvNextImageClassifier._model is not None:
            return

        model = timm.create_model(_MODEL_NAME, pretrained=True)
        model.to(ConvNextImageClassifier._device)
        model.eval()

        config = timm.data.resolve_data_config({}, model=model)
        transform = timm.data.create_transform(**config)

        ConvNextImageClassifier._model = model
        ConvNextImageClassifier._transform = transform
        ConvNextImageClassifier._labels = ImageNetInfo()

    def _classify_sync(self, image_bytes: bytes) -> ImageClassificationDto:
        self._ensure_loaded()
        model = ConvNextImageClassifier._model
        transform = ConvNextImageClassifier._transform
        labels = ConvNextImageClassifier._labels

        try:
            image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        except UnidentifiedImageError as e:
            raise ValueError(
                "이미지를 읽을 수 없습니다. 손상되었거나 지원하지 않는 형식입니다."
            ) from e

        tensor = transform(image).unsqueeze(0).to(ConvNextImageClassifier._device)

        with torch.no_grad():
            logits = model(tensor)
            probs = torch.softmax(logits, dim=-1)[0]

        top_probs, top_indices = torch.topk(probs, k=min(_TOP_K, probs.shape[0]))
        top5 = [
            TopKPredictionDto(
                label=labels.index_to_description(idx), score=float(score)
            )
            for score, idx in zip(top_probs.tolist(), top_indices.tolist(), strict=True)
        ]

        top1 = top5[0]
        return ImageClassificationDto(
            label=top1.label,
            confidence=top1.score,
            is_confident=top1.score >= _confidence_threshold(),
            top5=top5,
        )

    async def classify(self, image_bytes: bytes) -> ImageClassificationDto:
        return await asyncio.to_thread(self._classify_sync, image_bytes)
