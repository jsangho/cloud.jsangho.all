"""VideoMAE 어댑터의 프레임 샘플링 — decord → OpenCV 교체(2026-11-11) 회귀 검증.

모델은 로드하지 않는다. `_sample_frames` 만 실제 영상 바이트로 돌린다.
"""

import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

_APPS_DIR = str(Path(__file__).resolve().parents[2])
if _APPS_DIR not in sys.path:
    sys.path.insert(0, _APPS_DIR)

from ontology.adapter.outbound.videomae_video_classifier import (  # noqa: E402
    _NUM_FRAMES,
    VideoMaeVideoClassifier,
)

_W, _H = 64, 48


def _video_bytes(tmp_path: Path, n_frames: int) -> bytes:
    """프레임 i 의 B 채널 = i*8 인 MJPG 영상. 순서·색 변환을 함께 검사한다."""
    path = tmp_path / "clip.avi"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 10, (_W, _H))
    assert writer.isOpened()
    for i in range(n_frames):
        frame = np.zeros((_H, _W, 3), dtype=np.uint8)
        frame[:, :, 0] = i * 8  # OpenCV는 BGR — 0번 채널이 파랑
        writer.write(frame)
    writer.release()
    return path.read_bytes()


def test_samples_fixed_count_in_order_as_rgb(tmp_path: Path) -> None:
    frames = VideoMaeVideoClassifier()._sample_frames(_video_bytes(tmp_path, 30))

    assert len(frames) == _NUM_FRAMES
    assert frames[0].shape == (_H, _W, 3)
    blue = [int(f[:, :, 2].mean()) for f in frames]  # RGB로 바뀌었으면 2번 채널
    assert all(int(f[:, :, 0].mean()) < 4 for f in frames)
    assert blue == sorted(blue)
    assert blue[0] < 4
    assert abs(blue[-1] - 29 * 8) <= 4  # 마지막 프레임까지 닿는다 (MJPG 손실 허용)


def test_short_video_returns_every_frame(tmp_path: Path) -> None:
    frames = VideoMaeVideoClassifier()._sample_frames(_video_bytes(tmp_path, 5))
    assert len(frames) == 5


def test_garbage_bytes_raise_value_error() -> None:
    with pytest.raises(ValueError):
        VideoMaeVideoClassifier()._sample_frames(b"not a video")
