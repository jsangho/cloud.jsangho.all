from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class VideoTopKPredictionDto:
    label: str
    score: float


@dataclass(frozen=True)
class VideoClassificationDto:
    label: str
    confidence: float
    is_confident: bool
    top5: list[VideoTopKPredictionDto] = field(default_factory=list)
