from __future__ import annotations

import asyncio
import io
from typing import Any, ClassVar

import numpy as np
import torch
from core.matrix.vault_keymaker_secret_manager import get_keymaker
from decord import VideoReader, cpu
from transformers import VideoMAEForVideoClassification, VideoMAEImageProcessor

from ontology.app.dtos.video_classification_dto import (
    VideoClassificationDto,
    VideoTopKPredictionDto,
)
from ontology.app.ports.output.video_label_classifier import VideoLabelClassifier

# _docs/video-classifier-agent.md 2장 1순위 추천 모델(VideoMAE v2). Kinetics-400
# 사전학습 체크포인트로 3D CNN이 하던 "영상 클립 → 클래스" 분류를 대체한다.
# 커스텀 라벨셋 파인튜닝 전이므로 우선 사전학습 라벨(400 클래스)로 서빙한다.
_MODEL_NAME = "MCG-NJU/videomae-base-finetuned-kinetics"
_TOP_K = 5
_NUM_FRAMES = 16


def _confidence_threshold() -> float:
    return float(
        get_keymaker().get_secret("VIDEO_CLASSIFIER_CONFIDENCE_THRESHOLD", "0.5")
    )


class VideoMaeVideoClassifier(VideoLabelClassifier):
    """VideoMAE v2(Kinetics-400 사전학습) 기반 단일 라벨 비디오 분류 어댑터.

    모델·프로세서는 프로세스에서 한 번만 로드해 재사용한다(클래스 변수 캐시 —
    ConvNextImageClassifier와 동일한 패턴).
    """

    _model: ClassVar[torch.nn.Module | None] = None
    _processor: ClassVar[Any] = None
    _device: ClassVar[str] = "cuda" if torch.cuda.is_available() else "cpu"

    def _ensure_loaded(self) -> None:
        if VideoMaeVideoClassifier._model is not None:
            return

        processor = VideoMAEImageProcessor.from_pretrained(_MODEL_NAME)
        model = VideoMAEForVideoClassification.from_pretrained(_MODEL_NAME)
        model.to(VideoMaeVideoClassifier._device)
        model.eval()

        VideoMaeVideoClassifier._model = model
        VideoMaeVideoClassifier._processor = processor

    def _sample_frames(self, video_bytes: bytes) -> list[np.ndarray]:
        try:
            reader = VideoReader(io.BytesIO(video_bytes), ctx=cpu(0))
        except Exception as e:
            raise ValueError(
                "비디오를 읽을 수 없습니다. 손상되었거나 지원하지 않는 형식입니다."
            ) from e

        total_frames = len(reader)
        if total_frames == 0:
            raise ValueError("비디오에 프레임이 없습니다.")

        indices = np.linspace(0, total_frames - 1, num=min(_NUM_FRAMES, total_frames))
        indices = np.clip(indices, 0, total_frames - 1).astype(int)
        return list(reader.get_batch(indices).asnumpy())

    def _classify_sync(self, video_bytes: bytes) -> VideoClassificationDto:
        self._ensure_loaded()
        model = VideoMaeVideoClassifier._model
        processor = VideoMaeVideoClassifier._processor

        frames = self._sample_frames(video_bytes)
        inputs = processor(list(frames), return_tensors="pt").to(
            VideoMaeVideoClassifier._device
        )

        with torch.no_grad():
            logits = model(**inputs).logits[0]
            probs = torch.softmax(logits, dim=-1)

        top_probs, top_indices = torch.topk(probs, k=min(_TOP_K, probs.shape[0]))
        top5 = [
            VideoTopKPredictionDto(label=model.config.id2label[idx], score=float(score))
            for score, idx in zip(top_probs.tolist(), top_indices.tolist(), strict=True)
        ]

        top1 = top5[0]
        return VideoClassificationDto(
            label=top1.label,
            confidence=top1.score,
            is_confident=top1.score >= _confidence_threshold(),
            top5=top5,
        )

    async def classify(self, video_bytes: bytes) -> VideoClassificationDto:
        return await asyncio.to_thread(self._classify_sync, video_bytes)
