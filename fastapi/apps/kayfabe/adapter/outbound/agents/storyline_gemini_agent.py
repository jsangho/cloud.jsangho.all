"""서사 분석 에이전트 — 하네스 §10-T5.

대립 각본의 진행 방향·타이틀 명분·푸시 흐름으로 승자를 추론한다. 생성은 ontology
허브의 `GeminiGenerationUseCase`에 위임한다(§3-D7) — 스포크가 벤더 SDK를 직접 잡지 않는다.

**지식이 없으면 모델을 부르지 않는다.** 카드만 보고 서사를 논하는 것은 추측이고,
추측을 근거처럼 내보내면 나머지 두 축의 판단까지 오염된다.
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
from kayfabe.app.ports.output.storyline_analyst_port import StorylineAnalystPort
from kayfabe.domain.entities.agent_prediction import (
    AgentKind,
    AgentReport,
    AgentRuntime,
)
from ontology.app.ports.input.gemini_generation_use_case import GeminiGenerationUseCase

_NO_KNOWLEDGE = "참고할 서사 자료가 없습니다."

_PERSONA = (
    "당신은 WWE 각본의 흐름을 오래 지켜본 분석가입니다. "
    "아래 [자료]에 있는 사실만 근거로 이 경기의 승자를 추론하세요. "
    "판단 기준은 대립 각본의 진행 방향, 타이틀의 명분, 최근 푸시 흐름입니다. "
    "[자료]에 없는 내용을 지어내지 마세요."
)

#: 이 에이전트 **로직**의 판 (Phase 4). 프롬프트가 아니라 코드가 바뀔 때 올린다 —
#: 어떤 자료를 고르는지, 의견 없음으로 언제 낮추는지 같은 것들이다. 프롬프트 쪽은
#: `PROMPT_VERSION`이 알아서 따라가므로 여기 손대지 않는다.
#:
#: **파생값이 아니라 선언이다.** 올리는 것을 잊으면 틀린 값이 남는다.
AGENT_VERSION = "storyline@1"

#: 지시문에서 파생된다. 페르소나를 고치면 다음 예측부터 저절로 달라진다.
PROMPT_VERSION = prompt_version(_PERSONA)


class GeminiStorylineAnalyst(StorylineAnalystPort):
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
            # 모델을 부르지 않았으므로 모델·프롬프트 칸은 비운다. 그래도 어느 판의
            # 에이전트가 "자료 없음"이라고 판단했는지는 남긴다 — 선별 규칙이 바뀌면
            # 같은 코퍼스에서도 이 결과가 달라진다.
            return silent(
                AgentKind.STORYLINE,
                _NO_KNOWLEDGE,
                AgentRuntime(agent_version=AGENT_VERSION),
            )

        return await ask_for_report(
            self._generation_use_case,
            agent=AgentKind.STORYLINE,
            agent_version=AGENT_VERSION,
            prompt_version=PROMPT_VERSION,
            prompt=build_prompt(_PERSONA, context, chunks),
            context=context,
            chunks=chunks,
            gate=self._rate_gate,
            model=self._model,
            fallback_model=self._fallback_model,
        )
