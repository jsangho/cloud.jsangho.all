from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from kayfabe.app.dtos.wrestler_chat_dto import WrestlerChatCommand


class WrestlerChatUseCase(ABC):
    """`/kayfabe/wwe-chat/*` inbound(wrestler_chat_router) 입력 포트."""

    @abstractmethod
    def stream_chat(self, command: WrestlerChatCommand) -> AsyncIterator[str]:
        """WWE 로스터 정보를 근거로 스트리밍 답변한다."""
        ...
