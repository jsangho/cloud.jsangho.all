"""도구를 쥔 모델과 **한 걸음씩** 주고받는 명령·결과.

`gemini_generation_dto`는 "물어보고 답을 받는다"가 전부다. 그 모양으로는 에이전트를
만들 수 없다 — 에이전트는 답을 받기 전에 **무엇을 더 봐야 하는지 스스로 정하고**, 그
결정이 다음 요청의 재료가 되기 때문이다.

여기서 정한 원칙 둘.

1. **루프는 허브가 아니라 부르는 쪽이 돈다.** 이 포트는 한 걸음만 처리한다 — 도구를
   부르라는 요청이거나, 끝났다는 말이거나. 몇 걸음까지 갈지·어떤 도구를 실제로
   실행할지·언제 포기할지는 도메인 정책이고, 그것은 스포크의 앎이다(§3-D7이 검색을
   스포크에 둔 것과 같은 이유).
2. **상태를 허브에 두지 않는다.** 걸음마다 지금까지의 주고받음(`exchanges`) 전체를
   다시 보낸다. 대가는 알고 받는다 — 프롬프트가 걸음 수만큼 길어진다. 그 대신
   허브에 세션이 없어서 **같은 `ToolStepCommand`는 언제 보내도 같은 요청**이 되고,
   부르는 쪽이 대화를 잘라내거나 되돌리는 일을 자기 코드만 보고 할 수 있다.

**도구를 실행하는 것은 이 모듈의 일이 아니다.** 모델이 "이 이름으로 이 도구를 불러
달라"고 말하고, 부르는 쪽이 실행해 `ToolExchange`로 되돌려 준다. 그래서 허브는
스포크의 도구가 무엇을 하는지 영영 모른다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ToolDeclaration:
    """모델에게 알려 주는 도구 하나의 사용법."""

    name: str
    description: str
    #: JSON Schema. 벤더가 이 형식을 그대로 받으므로 여기서 변환하지 않는다.
    parameters: dict[str, Any]


@dataclass(frozen=True)
class ToolCall:
    """모델이 부르라고 말한 도구 하나."""

    name: str
    arguments: dict[str, Any]
    #: **벤더가 이 호출에 붙여 준 불투명 토큰.** 읽지도 만들지도 않고 그대로 되돌린다.
    #:
    #: 없으면 안 되는 값이다. 2026-09-28 실측에서 이것을 버렸다가 **둘째 걸음에서**
    #: 400이 났다: `Function call is missing a thought_signature in functionCall
    #: parts`. 추론 모델은 자기가 왜 그 도구를 불렀는지를 이 토큰에 담아 두고, 다음
    #: 요청에서 그것을 되받아야 대화를 이어 간다. 첫 걸음은 주고받음이 비어 있어
    #: 통과하므로 **루프를 두 걸음 이상 돌려 보지 않으면 드러나지 않는다.**
    #:
    #: 대화를 매 걸음 재조립하는 설계(`ToolStepCommand`)의 대가다 — 상태를 허브에
    #: 두지 않는 대신, 벤더가 상태로 쓰는 값을 이렇게 실어 나른다. 부르는 쪽은 이 칸을
    #: 건드리지 않고 `ToolExchange`에 담아 돌려주기만 한다.
    signature: bytes | None = None


@dataclass(frozen=True)
class ToolExchange:
    """부른 도구와 그 도구가 돌려준 값 한 쌍.

    `result`는 JSON으로 직렬화 가능해야 한다 — 그대로 모델에게 돌아간다. 도구가
    실패했다면 예외를 던지는 대신 실패를 적은 `result`를 담는 편이 낫다. 모델이 그것을
    읽고 다른 이름으로 다시 시도할 수 있기 때문이다.
    """

    call: ToolCall
    result: dict[str, Any]


@dataclass(frozen=True)
class ToolStepCommand:
    prompt: str
    tools: tuple[ToolDeclaration, ...]
    #: 지금까지의 주고받음. 비어 있으면 첫 걸음이다.
    exchanges: tuple[ToolExchange, ...] = ()
    #: 비우면 어댑터의 기본 모델. 한도가 모델 단위라 부르는 쪽이 나눠 쓸 수 있게 연다.
    model: str | None = None


@dataclass(frozen=True)
class ToolStep:
    """한 걸음의 결과. **둘 중 하나다** — 도구를 더 부르거나, 답을 내놓거나."""

    calls: tuple[ToolCall, ...] = ()
    text: str = ""
    #: 실제로 답한 모델. 기록하는 쪽이 설정값을 적으면 예비 모델이 답한 날의 기록이
    #: 거짓이 된다(`gemini_agent_support._generate`가 같은 이유로 이 값을 돌려준다).
    model: str | None = None

    @property
    def wants_tools(self) -> bool:
        return bool(self.calls)
