from __future__ import annotations

from abc import ABC, abstractmethod

from admin.app.dtos.langchain_chat_dto import LangchainChatCommand, LangchainChatResult


class LangchainUseCase(ABC):
    """`/langchain/chat` inbound(langchain_router) 입력 포트."""

    @abstractmethod
    async def chat(self, command: LangchainChatCommand) -> LangchainChatResult:
        """대화 이력을 받아 LangChain 기반 응답을 반환한다."""
        ...
