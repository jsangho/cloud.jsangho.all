from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from soccer.app.dtos.soccer_chat_dto import SoccerChatCommand


class SoccerChatPort(ABC):
    @abstractmethod
    def stream_chat(self, command: SoccerChatCommand) -> AsyncIterator[str]:
        pass
