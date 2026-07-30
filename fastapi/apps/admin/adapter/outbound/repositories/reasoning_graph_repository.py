from __future__ import annotations

from admin.adapter.outbound.graphs.reasoning_graph import build_reasoning_graph
from admin.app.dtos.langchain_chat_dto import LangchainChatCommand, LangchainChatResult
from admin.app.ports.output.graph_retrieval_port import GraphRetrievalPort
from admin.app.ports.output.reasoning_graph_port import ReasoningGraphPort
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI


class ReasoningGraphRepository(ReasoningGraphPort):
    """`reasoning_graph.py`의 StateGraph를 감싸는 어댑터.

    LangChain 메시지 변환·그래프 invoke는 여기서만 하고, 상위 유스케이스
    (`langgraph_interactor.py`)에는 포트(DTO)만 노출한다.
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
