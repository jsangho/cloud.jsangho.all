from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from ontology.app.dtos.exaone_generation_dto import ExaoneGenerationCommand


class ExaoneGenerationUseCase(ABC):
    """ontology 허브가 스포크 앱에 제공하는 범용 EXAONE 텍스트 생성 입력 포트.

    스포크는 도메인 지식(검색·프롬프트 구성)을 직접 소유하고, 이 포트를 통해서만
    ontology 허브의 LLM 생성 능력을 빌려 쓴다 (스포크 ↔ 스포크 직접 의존 금지).
    """

    @abstractmethod
    def stream_generate(
        self, command: ExaoneGenerationCommand
    ) -> AsyncIterator[str]: ...
