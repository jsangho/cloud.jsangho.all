from admin.adapter.outbound.repositories.graph_retrieval_repository import (
    GraphRetrievalRepository,
)
from admin.adapter.outbound.repositories.langchain_chat_repository import (
    LangchainChatRepository,
)
from admin.app.ports.input.langchain_use_case import LangchainUseCase
from admin.app.ports.output.graph_retrieval_port import GraphRetrievalPort
from admin.app.ports.output.langchain_chat_port import LangchainChatPort
from admin.app.use_cases.langchain_interactor import LangchainInteractor
from core.matrix.grid_architect_graph_manager import get_neo4j_session
from neo4j import AsyncSession

from fastapi import Depends
from ontology.app.ports.input.semantic_routing_use_case import SemanticRoutingUseCase
from ontology.dependencies.semantic_routing_provider import (
    get_semantic_routing_use_case,
)


def get_graph_retrieval_repository(
    session: AsyncSession = Depends(get_neo4j_session),
) -> GraphRetrievalPort:
    return GraphRetrievalRepository(session=session)


def get_langchain_chat_repository(
    semantic_routing_use_case: SemanticRoutingUseCase = Depends(
        get_semantic_routing_use_case
    ),
    graph_retrieval_port: GraphRetrievalPort = Depends(get_graph_retrieval_repository),
) -> LangchainChatPort:
    return LangchainChatRepository(
        semantic_routing_use_case=semantic_routing_use_case,
        graph_retrieval_port=graph_retrieval_port,
    )


def get_langchain_use_case(
    repository: LangchainChatPort = Depends(get_langchain_chat_repository),
) -> LangchainUseCase:
    return LangchainInteractor(repository=repository)
