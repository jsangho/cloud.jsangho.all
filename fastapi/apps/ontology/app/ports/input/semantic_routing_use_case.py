from __future__ import annotations

from abc import ABC, abstractmethod

from ontology.app.dtos.semantic_routing_dto import (
    RoutingDecision,
    SemanticRoutingCommand,
)


class SemanticRoutingUseCase(ABC):
    """ontology 허브가 스포크 앱에 제공하는 시맨틱 라우팅(의도 분류) 입력 포트.

    스포크는 이 포트로 질문의 destination/entities만 받아오고, 실제 CRUD·RAG·
    일반 대화 처리는 스포크가 각자 책임진다 (스포크 ↔ 스포크 직접 의존 금지).
    """

    @abstractmethod
    async def route(self, command: SemanticRoutingCommand) -> RoutingDecision: ...
