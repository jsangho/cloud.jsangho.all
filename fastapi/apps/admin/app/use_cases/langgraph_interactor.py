from __future__ import annotations

from admin.adapter.outbound.graphs.reasoning_graph import build_reasoning_graph
from admin.app.dtos.langchain_chat_dto import LangchainChatCommand, LangchainChatResult
from admin.app.ports.output.graph_retrieval_port import GraphRetrievalPort
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI


class LangGraphInteractor:
    """시맨틱 라우터가 `reasoning`으로 분류한 질문을 LangGraph StateGraph로 처리한다.

    `apps/admin/_docs/langgraph-harness.md` §3 1단계 스코프 — retrieve 노드는
    기존 `(:Document)` 텍스트만 조회하고, 근거 부족 시 최대 2회 재검색한다.
    """

    def __init__(
        self, graph_retrieval_port: GraphRetrievalPort, model: ChatGoogleGenerativeAI
    ) -> None:
        self._graph = build_reasoning_graph(graph_retrieval_port, model)

    async def run(
        self, command: LangchainChatCommand, entities: tuple[str, ...]
    ) -> LangchainChatResult:
        history: list[BaseMessage] = [
            HumanMessage(content=m.text)
            if m.role == "user"
            else AIMessage(content=m.text)
            for m in command.messages
        ]
        result = await self._graph.ainvoke(
            {
                "messages": history,
                "entities": list(entities),
                "retrieved_context": [],
                "retry_count": 0,
                "reply": "",
            }
        )
        return LangchainChatResult(reply=result["reply"])
