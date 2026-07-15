from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

RoutingDestination = Literal["crud", "exaone_rag", "gemini"]


@dataclass(frozen=True)
class SemanticRoutingCommand:
    question: str


@dataclass(frozen=True)
class RoutingDecision:
    destination: RoutingDestination
    entities: tuple[str, ...] = field(default_factory=tuple)
