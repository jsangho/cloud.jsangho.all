from __future__ import annotations

import logging

from admin.app.dtos.langchain_chat_dto import LangchainChatCommand, LangchainChatResult
from admin.app.ports.output.langchain_chat_port import LangchainChatPort
from core.matrix.vault_keymaker_secret_manager import get_keymaker
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from ontology.app.dtos.semantic_routing_dto import SemanticRoutingCommand
from ontology.app.ports.input.semantic_routing_use_case import SemanticRoutingUseCase

logger = logging.getLogger("uvicorn.error")

_MODEL_ID = "gemini-3.5-flash"


class LangchainChatRepository(LangchainChatPort):
    """ontology 허브의 시맨틱 라우팅(SemanticRoutingUseCase)으로 의도를 먼저
    판단한 뒤, langchain-google-genai(ChatGoogleGenerativeAI)로 대화 응답을
    생성하는 어댑터.

    스포크(admin)는 허브의 destination/entities만 받아오고, 실제 대화 생성은
    스포크가 소유한 LangChain 엔진이 책임진다 — 스포크 ↔ 스포크 직접 의존 없음.
    """

    def __init__(self, semantic_routing_use_case: SemanticRoutingUseCase) -> None:
        self._semantic_routing_use_case = semantic_routing_use_case
        model = ChatGoogleGenerativeAI(
            model=_MODEL_ID,
            google_api_key=get_keymaker().get_gemini_api_key(),
            thinking_budget=0,
        )
        # 최신 정보(스포츠 결과 등)를 학습 데이터가 아니라 실시간 검색으로 답하도록
        # Google Search grounding을 붙인다.
        self._model = model.bind_tools([{"google_search": {}}])

    async def generate(self, command: LangchainChatCommand) -> LangchainChatResult:
        user_messages = [m for m in command.messages if m.role == "user"]
        question = user_messages[-1].text if user_messages else ""

        decision = await self._semantic_routing_use_case.route(
            SemanticRoutingCommand(question=question)
        )
        logger.info(
            "[admin.langchain_chat] 시맨틱 라우팅 결과 | destination=%s | entities=%s",
            decision.destination,
            decision.entities,
        )

        history: list[BaseMessage] = []
        if decision.entities:
            history.append(
                SystemMessage(content=f"참고 키워드: {', '.join(decision.entities)}")
            )
        history.extend(
            HumanMessage(content=m.text)
            if m.role == "user"
            else AIMessage(content=m.text)
            for m in command.messages
        )

        logger.info("[admin.langchain_chat] LangChain 호출 시작 | model=%s", _MODEL_ID)
        response = await self._model.ainvoke(history)
        logger.info("[admin.langchain_chat] LangChain 호출 종료 | model=%s", _MODEL_ID)
        return LangchainChatResult(reply=response.text)
