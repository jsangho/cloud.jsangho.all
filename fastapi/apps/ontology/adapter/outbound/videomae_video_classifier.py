from __future__ import annotations

import asyncio
import tempfile
from typing import Any, ClassVar

import cv2
import numpy as np
import torch
from transformers import VideoMAEForVideoClassification, VideoMAEImageProcessor

from core.matrix.vault_keymaker_secret_manager import get_keymaker
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
        # decord 대신 OpenCV로 읽는다 — decord는 x86_64·Windows 휠만 있어 ARM
        # (Oracle A1) 이미지가 빌드되지 않았다 (2026-11-11). OpenCV는 파일 경로만
        # 받으므로 임시 파일을 거친다. decord와 같이 RGB로 돌려준다.
        with tempfile.NamedTemporaryFile(suffix=".video") as tmp:
            tmp.write(video_bytes)
            tmp.flush()
            capture = cv2.VideoCapture(tmp.name)
            try:
                if not capture.isOpened():
                    raise ValueError(
                        "비디오를 읽을 수 없습니다. "
                        "손상되었거나 지원하지 않는 형식입니다."
                    )
                total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
                if total_frames <= 0:
                    raise ValueError("비디오에 프레임이 없습니다.")

                indices = np.linspace(
                    0, total_frames - 1, num=min(_NUM_FRAMES, total_frames)
                ).astype(int)
                wanted = set(indices.tolist())
                picked: dict[int, np.ndarray] = {}
                # 앞에서부터 순서대로 넘긴다. 필요한 프레임만 디코딩해 메모리를
                # 프레임 수(_NUM_FRAMES)에 묶는다.
                for position in range(int(indices[-1]) + 1):
                    if not capture.grab():
                        break  # 메타데이터 프레임 수가 실제보다 클 때
                    if position in wanted:
                        ok, frame = capture.retrieve()
                        if ok:
                            picked[position] = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            finally:
                capture.release()

        if not picked:
            raise ValueError("비디오에 프레임이 없습니다.")
        # 끝쪽이 잘렸으면 마지막으로 읽은 프레임으로 채워 길이를 맞춘다.
        last = picked[max(picked)]
        return [picked.get(int(i), last) for i in indices]

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
