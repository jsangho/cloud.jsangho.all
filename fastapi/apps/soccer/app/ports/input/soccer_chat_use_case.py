from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from soccer.app.dtos.soccer_chat_dto import SoccerChatCommand


class SoccerChatUseCase(ABC):
    """`/soccer-chat/*` inbound(soccer_chat_router) 입력 포트."""

    @abstractmethod
    def stream_chat(self, command: SoccerChatCommand) -> AsyncIterator[str]:
        """축구 stadium/team/schedule/player 정보를 근거로 스트리밍 답변한다."""
        ...
