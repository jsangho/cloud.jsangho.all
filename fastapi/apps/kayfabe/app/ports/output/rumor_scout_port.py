from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from kayfabe.app.dtos.agent_prediction_dto import KnowledgeChunk, MatchContext
from kayfabe.domain.entities.agent_prediction import AgentReport


class RumorScoutPort(ABC):
    """루머 수집가 — 부상·복귀·계약 만료 같은 출전 변수에서 판단한다.

    **의견 없음이 기본값에 가깝다.** 대부분의 경기에는 판단을 뒤집을 소식이 없고,
    없는데 있는 척하면 예측 전체가 오염된다.
    """

    @abstractmethod
    async def analyze(
        self, context: MatchContext, knowledge: Sequence[KnowledgeChunk]
    ) -> AgentReport:
        """공개 소스 기반 리포트를 만든다.

        인용한 근거는 `AgentReport.sources`에 URL로 남긴다 — 출처 없는 루머는
        화면에 근거로 내보낼 수 없다(하네스 §3-D6).
        """
