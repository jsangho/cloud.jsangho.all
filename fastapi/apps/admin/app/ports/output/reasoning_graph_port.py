from __future__ import annotations

from abc import ABC, abstractmethod

from admin.app.dtos.langchain_chat_dto import LangchainChatCommand, LangchainChatResult


class ReasoningGraphPort(ABC):
    @abstractmethod
    async def run(
        self, command: LangchainChatCommand, entities: tuple[str, ...]
    ) -> LangchainChatResult:
        """LangGraph StateGraph를 실행해 reasoning 경로의 최종 응답을 만든다."""
        ...
