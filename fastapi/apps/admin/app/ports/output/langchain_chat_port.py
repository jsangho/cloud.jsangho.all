from __future__ import annotations

from abc import ABC, abstractmethod

from admin.app.dtos.langchain_chat_dto import LangchainChatCommand, LangchainChatResult


class LangchainChatPort(ABC):
    @abstractmethod
    async def generate(self, command: LangchainChatCommand) -> LangchainChatResult:
        """LangChain 모델을 호출해 다음 응답을 생성한다."""
        ...
