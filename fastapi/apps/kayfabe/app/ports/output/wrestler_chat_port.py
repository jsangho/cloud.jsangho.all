from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from kayfabe.app.dtos.wrestler_chat_dto import WrestlerChatCommand


class WrestlerChatPort(ABC):
    @abstractmethod
    def stream_chat(self, command: WrestlerChatCommand) -> AsyncIterator[str]:
        pass
