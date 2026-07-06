from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SpamClassificationDto:
    label: str
    confidence: float
    matched_keywords: list[str] = field(default_factory=list)
