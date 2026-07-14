from __future__ import annotations

from collections.abc import AsyncIterator

from kayfabe.app.dtos.wrestler_chat_dto import WrestlerChatCommand
from kayfabe.app.ports.input.wrestler_chat_use_case import WrestlerChatUseCase
from kayfabe.app.ports.output.wrestler_chat_port import WrestlerChatPort


class WrestlerChatInteractor(WrestlerChatUseCase):
    def __init__(self, repository: WrestlerChatPort) -> None:
        self.repository = repository

    async def stream_chat(self, command: WrestlerChatCommand) -> AsyncIterator[str]:
        async for chunk in self.repository.stream_chat(command):
            yield chunk
