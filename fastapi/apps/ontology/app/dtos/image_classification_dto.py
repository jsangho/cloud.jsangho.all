from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TopKPredictionDto:
    label: str
    score: float


@dataclass(frozen=True)
class ImageClassificationDto:
    label: str
    confidence: float
    is_confident: bool
    top5: list[TopKPredictionDto] = field(default_factory=list)
