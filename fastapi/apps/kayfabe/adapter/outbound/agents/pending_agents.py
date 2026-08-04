"""T4·T5가 채울 자리를 잡아 두는 임시 어댑터.

**아직 분석기를 붙이지 않았다는 사실을 정직하게 표현한다.** 세 에이전트가 전부
"의견 없음"을 내면 코디네이터가 북메이커 배당으로 강등하고, 응답에 `source =
bookmaker_fallback`이 실린다 — 화면은 이 값을 보고 "AI 분석"이라고 말하지 않을 수
있다.

예외를 던지지 않고 의견 없음을 내는 이유: 실패가 아니라 **아직 판단할 근거가 없는
정상 상태**이기 때문이다. 예외로 만들면 로그가 경보로 가득 차고, 진짜 엔진 장애와
구분되지 않는다.
"""

from __future__ import annotations

from collections.abc import Sequence

from kayfabe.app.dtos.agent_prediction_dto import KnowledgeChunk, MatchContext
from kayfabe.app.ports.output.prediction_knowledge_port import PredictionKnowledgePort
from kayfabe.app.ports.output.rumor_scout_port import RumorScoutPort
from kayfabe.app.ports.output.storyline_analyst_port import StorylineAnalystPort
from kayfabe.domain.entities.agent_prediction import AgentKind, AgentReport

_NOT_WIRED = "분석기가 아직 연결되지 않았습니다."


def _silent(agent: AgentKind) -> AgentReport:
    return AgentReport(agent=agent, pick=None, weight=0.0, summary=_NOT_WIRED)


class PendingStorylineAnalyst(StorylineAnalystPort):
    async def analyze(
        self, context: MatchContext, knowledge: Sequence[KnowledgeChunk]
    ) -> AgentReport:
        return _silent(AgentKind.STORYLINE)


class PendingRumorScout(RumorScoutPort):
    async def analyze(
        self, context: MatchContext, knowledge: Sequence[KnowledgeChunk]
    ) -> AgentReport:
        return _silent(AgentKind.RUMOR)


class EmptyPredictionKnowledge(PredictionKnowledgePort):
    """T3에서 지식을 적재하기 전까지는 검색 결과가 비어 있다 — 실패가 아니다."""

    async def search(self, *, query: str, top_k: int) -> list[KnowledgeChunk]:
        return []
