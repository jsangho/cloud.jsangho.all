from __future__ import annotations

from abc import ABC, abstractmethod

from kayfabe.app.dtos.agent_prediction_dto import MatchContext
from kayfabe.domain.entities.agent_prediction import AgentReport


class OddsScoutPort(ABC):
    """오즈 수집가 — 배당의 절대 수준과 변동 방향을 읽는다.

    다른 두 에이전트와 달리 **RAG 지식을 받지 않는다.** 판단 근거가 숫자라
    검색이 필요 없고, 그래서 LLM 없이도 구현할 수 있다.
    """

    @abstractmethod
    async def analyze(self, context: MatchContext) -> AgentReport:
        """배당 근거로 리포트를 만든다.

        `context.bookmaker_decimal`이 없으면 `AgentReport(pick=None)`이다.
        외부 배당 조회가 실패했으면 `AgentUnavailableError`.
        """
