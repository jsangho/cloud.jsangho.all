"""`google-genai`로 도구 호출 한 걸음을 처리하는 어댑터.

**자동 함수 호출을 끈다.** SDK는 파이썬 함수를 그대로 넘기면 스스로 부르고 루프까지
돌아 주는데, 그러면 도구 실행이 벤더 SDK 안에서 일어난다. 이 저장소에서 그것은 두 가지를
잃는 일이다 — 걸음 수 상한을 우리가 못 걸고, 모델이 무엇을 봤는지(=인용 검증의 재료)를
우리가 못 모은다. 그래서 선언만 넘기고 실행은 부르는 쪽이 한다.

**대화를 매 걸음 다시 조립한다.** 허브에 세션을 두지 않기로 한 결정(`gemini_tool_dto`)의
구현이다. 재조립은 순수 함수라, 같은 `exchanges`는 언제나 같은 `contents`가 된다.
"""

from __future__ import annotations

import logging
import os

from core.matrix.vault_keymaker_secret_manager import (
    DEFAULT_GEMINI_MODEL_ID,
    get_keymaker,
)
from google import genai
from google.genai import types

from ontology.app.dtos.gemini_tool_dto import (
    ToolCall,
    ToolDeclaration,
    ToolStep,
    ToolStepCommand,
)
from ontology.app.ports.output.gemini_tool_port import GeminiToolPort

logger = logging.getLogger("uvicorn.error")


def _default_model() -> str:
    """`gemini_generator._default_model`과 같은 규칙 — 모델 ID를 코드에 박지 않는다."""
    return (os.getenv("GEMINI_MODEL") or "").strip() or DEFAULT_GEMINI_MODEL_ID


def _declaration(tool: ToolDeclaration) -> types.FunctionDeclaration:
    return types.FunctionDeclaration(
        name=tool.name,
        description=tool.description,
        parameters=tool.parameters,
    )


def _contents(command: ToolStepCommand) -> list[types.Content]:
    """프롬프트 + 지금까지의 주고받음 → 벤더 대화 형식.

    도구 응답의 `role`이 `"user"`인 것은 벤더 규약이다 — 모델이 말한 것(`model`)에
    대한 답을 사람 쪽에서 돌려주는 모양이다.
    """
    contents = [
        types.Content(role="user", parts=[types.Part.from_text(text=command.prompt)])
    ]
    for exchange in command.exchanges:
        contents.append(
            types.Content(
                role="model",
                parts=[
                    types.Part(
                        function_call=types.FunctionCall(
                            name=exchange.call.name, args=exchange.call.arguments
                        ),
                        # **불투명 토큰을 그대로 되돌린다.** 빠뜨리면 둘째 걸음에서
                        # 400이 난다(`ToolCall.signature` 주석의 실측). 첫 걸음은
                        # 여기를 지나지 않으므로 한 걸음만 돌려서는 드러나지 않는다.
                        thought_signature=exchange.call.signature,
                    )
                ],
            )
        )
        contents.append(
            types.Content(
                role="user",
                parts=[
                    types.Part.from_function_response(
                        name=exchange.call.name, response=exchange.result
                    )
                ],
            )
        )
    return contents


class GeminiToolCaller(GeminiToolPort):
    """`client`는 테스트가 갈아 끼우는 자리다 — 기본값이 실제 동작이다."""

    def __init__(self, *, client: genai.Client | None = None) -> None:
        self._client = client or genai.Client(
            api_key=get_keymaker().get_gemini_api_key()
        )

    async def next_step(self, command: ToolStepCommand) -> ToolStep:
        model = command.model or _default_model()
        config = types.GenerateContentConfig(
            tools=[
                types.Tool(
                    function_declarations=[_declaration(tool) for tool in command.tools]
                )
            ],
            # 실행은 우리가 한다. 위 독스트링의 이유다.
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                disable=True
            ),
        )
        response = await self._client.aio.models.generate_content(
            model=model, contents=_contents(command), config=config
        )
        return _to_step(response, model)


def _to_step(response: object, model: str) -> ToolStep:
    """응답에서 도구 호출과 글을 갈라낸다.

    **도구 호출이 하나라도 있으면 글은 버린다.** 모델은 호출과 함께 "이제 찾아
    보겠습니다" 같은 말을 얹는 날이 있는데, 그것을 최종 답으로 읽으면 루프가 한 걸음
    만에 끝난다. 끝났다는 신호는 **호출이 없는 것** 하나뿐이다.
    """
    calls: list[ToolCall] = []
    pieces: list[str] = []

    for part in _parts(response):
        call = getattr(part, "function_call", None)
        if call is not None and getattr(call, "name", None):
            calls.append(
                ToolCall(
                    name=call.name,
                    arguments=dict(call.args or {}),
                    # 호출과 **같은 파트**에 실려 온다. 여기서 놓치면 다음 걸음이 400이다.
                    signature=getattr(part, "thought_signature", None),
                )
            )
            continue
        text = getattr(part, "text", None)
        if text:
            pieces.append(text)

    if calls:
        return ToolStep(calls=tuple(calls), model=model)
    return ToolStep(text="".join(pieces).strip(), model=model)


def _parts(response: object) -> list:
    """후보가 없거나 비어 있으면 빈 목록 — 부르는 쪽이 "답 없음"으로 다룬다.

    안전 필터에 걸리면 `candidates`가 비거나 `content`가 `None`으로 온다. 그때
    `AttributeError`로 터지면 경기 하나가 아니라 실행 전체가 멈춘다.
    """
    candidates = getattr(response, "candidates", None) or []
    if not candidates:
        return []
    content = getattr(candidates[0], "content", None)
    return list(getattr(content, "parts", None) or [])
