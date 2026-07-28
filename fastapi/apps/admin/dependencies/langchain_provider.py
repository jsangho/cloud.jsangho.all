from admin.adapter.outbound.repositories.langchain_chat_repository import (
    LangchainChatRepository,
)
from admin.app.ports.input.langchain_use_case import LangchainUseCase
from admin.app.ports.output.langchain_chat_port import LangchainChatPort
from admin.app.use_cases.langchain_interactor import LangchainInteractor

from fastapi import Depends
from ontology.app.ports.input.semantic_routing_use_case import SemanticRoutingUseCase
from ontology.dependencies.semantic_routing_provider import (
    get_semantic_routing_use_case,
)


def get_langchain_chat_repository(
    semantic_routing_use_case: SemanticRoutingUseCase = Depends(
        get_semantic_routing_use_case
    ),
) -> LangchainChatPort:
    return LangchainChatRepository(semantic_routing_use_case=semantic_routing_use_case)


def get_langchain_use_case(
    repository: LangchainChatPort = Depends(get_langchain_chat_repository),
) -> LangchainUseCase:
    return LangchainInteractor(repository=repository)
