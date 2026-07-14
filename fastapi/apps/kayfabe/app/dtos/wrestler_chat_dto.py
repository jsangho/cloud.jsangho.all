from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WrestlerChatTurnDto:
    role: str
    text: str


@dataclass(frozen=True)
class WrestlerChatCommand:
    messages: tuple[WrestlerChatTurnDto, ...]
