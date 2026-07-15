from __future__ import annotations

from collections.abc import AsyncIterator

from soccer.app.dtos.soccer_chat_dto import SoccerChatCommand
from soccer.app.ports.input.soccer_chat_use_case import SoccerChatUseCase
from soccer.app.ports.output.soccer_chat_port import SoccerChatPort


class SoccerChatInteractor(SoccerChatUseCase):
    def __init__(self, repository: SoccerChatPort) -> None:
        self.repository = repository

    async def stream_chat(self, command: SoccerChatCommand) -> AsyncIterator[str]:
        async for chunk in self.repository.stream_chat(command):
            yield chunk
