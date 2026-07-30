from __future__ import annotations

from typing import Literal, TypedDict

from admin.app.ports.output.graph_retrieval_port import GraphRetrievalPort
from langchain_core.messages import BaseMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

_MAX_RETRIES = 2
_MAX_ATTEMPTS = 1 + _MAX_RETRIES
_CONTEXT_CHAR_LIMIT = 2000


class ReasoningState(TypedDict):
    messages: list[BaseMessage]
    entities: list[str]
    retrieved_context: list[str]
    retry_count: int
    reply: str


def build_reasoning_graph(
    port: GraphRetrievalPort, model: ChatGoogleGenerativeAI
) -> CompiledStateGraph:
    """`langgraph-harness.md` §3 StateGraph — retrieve/answer 노드 + 조건부 재검색 루프.

    근거(:Document) 텍스트가 비어 있고 재시도 여력이 남아 있으면 retrieve로
    되돌아간다(최초 시도는 entities로 필터링, 재시도는 최근 문서로 폭을 넓힌다).
    """

    async def retrieve(state: ReasoningState) -> dict:
        attempt = state["retry_count"]
        keywords = state["entities"] if attempt == 0 else []
        docs = await port.search_documents(keywords)
        return {"retrieved_context": docs, "retry_count": attempt + 1}

    def route_after_retrieve(state: ReasoningState) -> Literal["retrieve", "answer"]:
        if not state["retrieved_context"] and state["retry_count"] < _MAX_ATTEMPTS:
            return "retrieve"
        return "answer"

    async def answer(state: ReasoningState) -> dict:
        context_block = "\n\n---\n\n".join(
            text[:_CONTEXT_CHAR_LIMIT] for text in state["retrieved_context"]
        )
        if context_block:
            system_text = (
                "아래는 문서 저장소에서 조회한 참고 자료다. 이 자료를 근거로 "
                "종합해서 답변하라. 자료에 없는 내용은 추측하지 말고 모른다고 답하라.\n\n"
                f"{context_block}"
            )
        else:
            system_text = (
                "문서 저장소에서 관련 자료를 찾지 못했다. 근거 문서가 없다는 점을 "
                "답변에 명시하고, 일반 지식 범위에서만 신중하게 답하라."
            )
        history: list[BaseMessage] = [
            SystemMessage(content=system_text),
            *state["messages"],
        ]
        response = await model.ainvoke(history)
        return {"reply": response.text}

    graph = StateGraph(ReasoningState)
    graph.add_node("retrieve", retrieve)
    graph.add_node("answer", answer)
    graph.add_edge(START, "retrieve")
    graph.add_conditional_edges(
        "retrieve",
        route_after_retrieve,
        {"retrieve": "retrieve", "answer": "answer"},
    )
    graph.add_edge("answer", END)
    return graph.compile()
