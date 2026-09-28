from __future__ import annotations

from abc import ABC, abstractmethod

from ontology.app.dtos.gemini_tool_dto import ToolStep, ToolStepCommand


class GeminiToolUseCase(ABC):
    """허브가 스포크에 제공하는 **도구 호출 한 걸음**.

    스포크는 도구의 뜻(무엇을 조회하는가·언제 멈추는가)을 직접 소유하고, 모델과
    말을 주고받는 기계적인 일만 이 포트로 빌려 쓴다 — `GeminiGenerationUseCase`와
    같은 경계다(§3-D7).
    """

    @abstractmethod
    async def next_step(self, command: ToolStepCommand) -> ToolStep: ...
