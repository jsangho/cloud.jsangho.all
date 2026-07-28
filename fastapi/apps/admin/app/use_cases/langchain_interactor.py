from __future__ import annotations

from admin.app.dtos.langchain_chat_dto import LangchainChatCommand, LangchainChatResult
from admin.app.ports.input.langchain_use_case import LangchainUseCase
from admin.app.ports.output.langchain_chat_port import LangchainChatPort


class LangchainInteractor(LangchainUseCase):
    def __init__(self, repository: LangchainChatPort):
        self.repository = repository

    async def chat(self, command: LangchainChatCommand) -> LangchainChatResult:
        return await self.repository.generate(command)
