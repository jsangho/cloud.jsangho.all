from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from kayfabe.app.dtos.agent_prediction_dto import KnowledgeChunk, MatchContext
from kayfabe.domain.entities.agent_prediction import AgentReport


class StorylineAnalystPort(ABC):
    """서사 분석가 — 대립 각본·명분·푸시 흐름으로 승자를 추론한다.

    유스케이스는 이 뒤에 Gemini가 있는지 다른 모델이 있는지 모른다(하네스 §3-D2).
    """

    @abstractmethod
    async def analyze(
        self, context: MatchContext, knowledge: Sequence[KnowledgeChunk]
    ) -> AgentReport:
        """서사 근거로 리포트를 만든다.

        참고할 서사가 없으면 `AgentReport(pick=None)`을 돌려준다 — 억지로 한쪽을
        고르지 않는다. 엔진이 죽었으면 `AgentUnavailableError`.
        """
