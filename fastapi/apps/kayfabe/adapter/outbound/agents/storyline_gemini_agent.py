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
    describe_knowledge,
    describe_match,
    json_rule,
    shared_rate_gate,
    silent,
    usable_knowledge,
)
from kayfabe.app.dtos.agent_prediction_dto import KnowledgeChunk, MatchContext
from kayfabe.app.ports.output.storyline_analyst_port import StorylineAnalystPort
from kayfabe.domain.entities.agent_prediction import AgentKind, AgentReport
from ontology.app.ports.input.gemini_generation_use_case import GeminiGenerationUseCase

_NO_KNOWLEDGE = "참고할 서사 자료가 없습니다."

_PERSONA = (
    "당신은 WWE 각본의 흐름을 오래 지켜본 분석가입니다. "
    "아래 [자료]에 있는 사실만 근거로 이 경기의 승자를 추론하세요. "
    "판단 기준은 대립 각본의 진행 방향, 타이틀의 명분, 최근 푸시 흐름입니다. "
    "[자료]에 없는 내용을 지어내지 마세요."
)


class GeminiStorylineAnalyst(StorylineAnalystPort):
    def __init__(
        self,
        generation_use_case: GeminiGenerationUseCase,
        *,
        model: str | None = None,
        rate_gate: RateGate | None = None,
    ) -> None:
        self._generation_use_case = generation_use_case
        # 무료 등급 한도가 모델 단위라, 두 에이전트가 다른 모델을 쓰면 한도를 나눠 갖는다.
        self._model = model
        # 기본값은 두 에이전트가 공유하는 게이트다 — 한도는 모델 단위이기 때문이다.
        self._rate_gate = rate_gate or shared_rate_gate

    async def analyze(
        self, context: MatchContext, knowledge: Sequence[KnowledgeChunk]
    ) -> AgentReport:
        chunks = usable_knowledge(knowledge)
        if not chunks:
            return silent(AgentKind.STORYLINE, _NO_KNOWLEDGE)

        prompt = (
            f"{_PERSONA}\n\n"
            f"[경기]\n{describe_match(context)}\n\n"
            f"[자료]\n{describe_knowledge(chunks)}\n\n"
            f"{json_rule()}"
        )
        return await ask_for_report(
            self._generation_use_case,
            agent=AgentKind.STORYLINE,
            prompt=prompt,
            context=context,
            chunks=chunks,
            gate=self._rate_gate,
            model=self._model,
        )
