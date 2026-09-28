from __future__ import annotations

from ontology.adapter.outbound.gemini_tool_caller import GeminiToolCaller
from ontology.app.ports.input.gemini_tool_use_case import GeminiToolUseCase
from ontology.app.use_cases.gemini_tool_interactor import GeminiToolInteractor


def get_gemini_tool_use_case() -> GeminiToolUseCase:
    """`Depends`가 아니다 — 지금 호출자는 검증 스크립트뿐이다.

    `get_wiki_title_port`와 같은 이유로 맨 팩토리다. 요청 컨텍스트 밖에서 도는 경로다.
    """
    return GeminiToolInteractor(caller=GeminiToolCaller())
