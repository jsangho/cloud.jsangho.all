from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator

from titanic.app.dtos.crew_smith_captain_dto import (
    ChatResponse,
    SmithCaptainChatCommand,
    SmithCaptainQuery,
    SmithCaptainResponse,
)


class SmithCaptainPort(ABC):
    @abstractmethod
    async def introduce_myself(self, query: SmithCaptainQuery) -> SmithCaptainResponse:
        pass

    @abstractmethod
    async def chat(self, command: SmithCaptainChatCommand) -> ChatResponse:
        pass

    @abstractmethod
    def chat_stream(self, command: SmithCaptainChatCommand) -> Iterator[str]:
        pass
