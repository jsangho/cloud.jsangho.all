"""루머 수집 에이전트 — 하네스 §10-T5.

**서사와 이 축을 가르는 것은 시제다** (2026-09-30에 이 말로 정리했다).
서사는 **일어난 일**을 읽고, 루머는 **일어날 일**을 읽는다. 방송에서 각본이 어디까지
왔는지는 저쪽 몫이고, 이쪽은 "앞으로 어떻게 될 것이라고 **보도된** 사실"만 본다.

그 시제 아래 두 갈래가 들어온다.

* **나설 수 있는가** — 부상·복귀·계약 만료·결장 발표
* **어디로 가기로 했는가** — 단체가 정했다고 보도된 푸시·타이틀 계획 (2026-09-30 추가)

둘째를 넣기 전에는 부상 계열만 봤는데, 그것만으로는 대부분의 경기에서 할 말이 없었다.
레슬링 저널리즘이 실제로 내는 정보의 큰 축이 "백스테이지에서 무엇을 하기로 했나"이고,
그것은 방송된 각본에서 추론한 것이 아니라 **보도된 사실**이므로 이 축의 것이다.

**경계는 '보도되었는가'이지 '미래에 관한 것인가'가 아니다.** 자료를 읽고 스스로
추론한 방향은 사실이 아니다 — 그것을 여기서 허용하면 이 축이 서사의 복제가 되고,
합성 단계에서 같은 근거가 두 표를 갖는다.

없는 소식을 있는 것처럼 만들면 서사·오즈의 판단까지 끌어내리므로, 프롬프트에서도
"그런 사실이 없으면 null"을 명시한다. 의견 없음은 고장이 아니다(§13-Q1).
"""

from __future__ import annotations

from collections.abc import Sequence

from kayfabe.adapter.outbound.agents.gemini_agent_support import (
    RateGate,
    ask_for_report,
    build_prompt,
    prompt_version,
    shared_rate_gate,
    silent,
    usable_knowledge,
)
from kayfabe.app.dtos.agent_prediction_dto import KnowledgeChunk, MatchContext
from kayfabe.app.ports.output.rumor_scout_port import RumorScoutPort
from kayfabe.domain.entities.agent_prediction import (
    AgentKind,
    AgentReport,
    AgentRuntime,
)
from ontology.app.ports.input.gemini_generation_use_case import GeminiGenerationUseCase

_NO_KNOWLEDGE = "참고할 소식이 없습니다."

_PERSONA = (
    "당신은 공개된 소식만 다루는 프로레슬링 취재 기자입니다. "
    "아래 [자료]에서 앞으로 어떻게 될 것이라고 보도된 사실만 찾으세요. 두 갈래입니다. "
    "(1) 나설 수 있는가 — 부상, 복귀, 계약 만료, 결장 발표. "
    "(2) 어디로 가기로 했는가 — 단체가 정했다고 보도된 푸시나 타이틀 계획, "
    "내부에서 유력하다고 전해진 방향. "
    "둘 다 자료가 그렇게 보도했을 때만 사실로 칩니다. 누가 전한 이야기인지 자료에 "
    "적혀 있어야 합니다. "
    "이미 방송된 일에서 당신이 추론한 것은 사실이 아닙니다 — 지난 경기 결과나 각본의 "
    "흐름으로 승자를 고르지 마세요. 그것은 서사 분석가의 몫입니다. "
    "그런 사실이 없으면 pick을 null로 두세요."
)

#: 이 에이전트 **로직**의 판 (Phase 4). 선언값이라 손으로 올린다 — 자세한 것은
#: `AgentRuntime` 독스트링.
#:
#: **2026-09-30의 페르소나 확장에는 올리지 않았다.** 바뀐 것이 지시문뿐이고 코드는
#: 그대로라, 그 변화는 아래 `PROMPT_VERSION`이 해시로 알아서 잡는다. 여기까지 같이
#: 올리면 같은 사실이 두 칸에 적혀 나중에 어느 쪽이 무엇을 뜻하는지 흐려진다.
AGENT_VERSION = "rumor@1"

#: 지시문에서 파생된다. 서사와 페르소나가 달라 값도 다르다.
PROMPT_VERSION = prompt_version(_PERSONA)


class GeminiRumorScout(RumorScoutPort):
    def __init__(
        self,
        generation_use_case: GeminiGenerationUseCase,
        *,
        model: str | None = None,
        fallback_model: str | None = None,
        rate_gate: RateGate | None = None,
    ) -> None:
        self._generation_use_case = generation_use_case
        # 무료 등급 한도가 모델 단위라, 두 에이전트가 다른 모델을 쓰면 한도를 나눠 갖는다.
        self._model = model
        # 주 모델이 혼잡할 때 마지막 시도를 넘길 곳.
        self._fallback_model = fallback_model
        # 기본값은 두 에이전트가 공유하는 게이트다 — 한도는 모델 단위이기 때문이다.
        self._rate_gate = rate_gate or shared_rate_gate

    async def analyze(
        self, context: MatchContext, knowledge: Sequence[KnowledgeChunk]
    ) -> AgentReport:
        chunks = usable_knowledge(knowledge)
        if not chunks:
            # 모델을 부르지 않았다 — 모델·프롬프트 칸은 비우고 판만 남긴다.
            return silent(
                AgentKind.RUMOR,
                _NO_KNOWLEDGE,
                AgentRuntime(agent_version=AGENT_VERSION),
            )

        return await ask_for_report(
            self._generation_use_case,
            agent=AgentKind.RUMOR,
            agent_version=AGENT_VERSION,
            prompt_version=PROMPT_VERSION,
            prompt=build_prompt(_PERSONA, context, chunks),
            context=context,
            chunks=chunks,
            gate=self._rate_gate,
            model=self._model,
            fallback_model=self._fallback_model,
        )
