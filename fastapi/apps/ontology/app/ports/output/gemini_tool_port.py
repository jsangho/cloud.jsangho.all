from __future__ import annotations

from abc import ABC, abstractmethod

from ontology.app.dtos.gemini_tool_dto import ToolStep, ToolStepCommand


class GeminiToolPort(ABC):
    """도구를 쥔 모델과 한 걸음 주고받는 출력 포트.

    `GeminiGenerationPort`와 나란히 두고 합치지 않는다. 저쪽은 스트리밍이 계약의
    일부이고(화면에 글자가 흐른다), 이쪽은 **한 걸음이 원자 단위**다 — 도구 호출
    요청은 쪼개서 흘려보낼 수 없다.
    """

    @abstractmethod
    async def next_step(self, command: ToolStepCommand) -> ToolStep: ...
