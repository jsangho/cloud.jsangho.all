from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SoccerChatTurnDto:
    role: str
    text: str


@dataclass(frozen=True)
class SoccerChatCommand:
    messages: tuple[SoccerChatTurnDto, ...]
