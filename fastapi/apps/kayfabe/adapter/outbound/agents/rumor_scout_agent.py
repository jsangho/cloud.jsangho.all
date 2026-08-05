"""루머 수집 에이전트 — 하네스 §10-T5.

부상·복귀·계약 만료처럼 **출전 여부를 흔드는 소식**만 본다. 대부분의 경기에는 그런
소식이 없고, 그때 "의견 없음"을 내는 것이 정상 동작이다(§13-Q1: 공개 소스만 쓰기로 한
결정의 대가).

없는 소식을 있는 것처럼 만들면 서사·오즈의 판단까지 끌어내리므로, 프롬프트에서도
"관련 소식이 없으면 null"을 명시한다.
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
from kayfabe.app.ports.output.rumor_scout_port import RumorScoutPort
from kayfabe.domain.entities.agent_prediction import AgentKind, AgentReport
from ontology.app.ports.input.gemini_generation_use_case import GeminiGenerationUseCase

_NO_KNOWLEDGE = "참고할 소식이 없습니다."

_PERSONA = (
    "당신은 공개된 소식만 다루는 프로레슬링 취재 기자입니다. "
    "아래 [자료]에서 이 경기의 출전 여부에 영향을 주는 사실만 찾으세요 — "
    "부상, 복귀, 계약 만료, 결장 발표 같은 것입니다. "
    "그런 사실이 없으면 pick을 null로 두세요. "
    "각본의 인기나 인상만으로 승자를 고르지 마세요 — 그것은 당신의 일이 아닙니다."
)


class GeminiRumorScout(RumorScoutPort):
    def __init__(
        self,
        generation_use_case: GeminiGenerationUseCase,
        *,
        rate_gate: RateGate | None = None,
    ) -> None:
        self._generation_use_case = generation_use_case
        # 기본값은 두 에이전트가 공유하는 게이트다 — 한도는 모델 단위이기 때문이다.
        self._rate_gate = rate_gate or shared_rate_gate

    async def analyze(
        self, context: MatchContext, knowledge: Sequence[KnowledgeChunk]
    ) -> AgentReport:
        chunks = usable_knowledge(knowledge)
        if not chunks:
            return silent(AgentKind.RUMOR, _NO_KNOWLEDGE)

        prompt = (
            f"{_PERSONA}\n\n"
            f"[경기]\n{describe_match(context)}\n\n"
            f"[자료]\n{describe_knowledge(chunks)}\n\n"
            f"{json_rule()}"
        )
        return await ask_for_report(
            self._generation_use_case,
            agent=AgentKind.RUMOR,
            prompt=prompt,
            context=context,
            chunks=chunks,
            gate=self._rate_gate,
        )
