from __future__ import annotations

from admin.app.dtos.langchain_chat_dto import LangchainChatCommand, LangchainChatResult
from admin.app.ports.output.reasoning_graph_port import ReasoningGraphPort


class LangGraphInteractor:
    """시맨틱 라우터가 `reasoning`으로 분류한 질문을 그래프 오케스트레이션
    포트(`ReasoningGraphPort`)로 위임하는 유스케이스.

    `apps/admin/_docs/langgraph-harness.md` §3 1단계 스코프. LangGraph·
    LangChain 등 프레임워크 타입은 포트 뒤(어댑터)에만 있고 이 파일에는
    없다 — `fastapi/CLAUDE.md` §2 `adapter → app → domain` 방향 규칙.
    """

    def __init__(self, reasoning_graph_port: ReasoningGraphPort) -> None:
        self._reasoning_graph_port = reasoning_graph_port

    async def run(
        self, command: LangchainChatCommand, entities: tuple[str, ...]
    ) -> LangchainChatResult:
        return await self._reasoning_graph_port.run(command, entities)
