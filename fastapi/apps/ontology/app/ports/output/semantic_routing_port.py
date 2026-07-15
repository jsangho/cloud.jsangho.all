from __future__ import annotations

from abc import ABC, abstractmethod

from ontology.app.dtos.semantic_routing_dto import SemanticRoutingCommand


class SemanticRoutingPort(ABC):
    """의도 분류 LLM 호출 결과(raw JSON 문자열)를 반환하는 출력 포트.

    파싱·가드레일(기본 destination 폴백)은 어댑터가 아니라 인터랙터의
    책임이다 — 어댑터는 순수 I/O만 담당한다.
    """

    @abstractmethod
    async def classify(self, command: SemanticRoutingCommand) -> str: ...
