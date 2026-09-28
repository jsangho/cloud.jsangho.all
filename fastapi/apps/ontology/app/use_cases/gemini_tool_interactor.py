from __future__ import annotations

import logging

from ontology.app.dtos.gemini_tool_dto import ToolStep, ToolStepCommand
from ontology.app.ports.input.gemini_tool_use_case import GeminiToolUseCase
from ontology.app.ports.output.gemini_tool_port import GeminiToolPort

logger = logging.getLogger("uvicorn.error")


class GeminiToolInteractor(GeminiToolUseCase):
    """허브 진입 로그만 얹는다 — 판단은 포트와 부르는 쪽에 있다.

    **프롬프트 원문도 도구 인자도 로그에 남기지 않는다**(§4-10 · §11-6). 걸음마다
    남는 것은 길이와 도구 이름뿐이고, 그것으로 "몇 걸음 돌았고 무엇을 봤나"까지는
    사후에 물을 수 있다.
    """

    def __init__(self, caller: GeminiToolPort) -> None:
        self._caller = caller

    async def next_step(self, command: ToolStepCommand) -> ToolStep:
        logger.info(
            "[ontology.gemini_tool] 허브 진입 | prompt_len=%d | tools=%d | 주고받음=%d",
            len(command.prompt),
            len(command.tools),
            len(command.exchanges),
        )
        step = await self._caller.next_step(command)
        logger.info(
            "[ontology.gemini_tool] 허브 완료 | 호출=%s | text_len=%d",
            [call.name for call in step.calls] or "없음",
            len(step.text),
        )
        return step
