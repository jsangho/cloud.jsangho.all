from __future__ import annotations

from abc import ABC, abstractmethod

from kayfabe.app.dtos.agent_prediction_dto import (
    AgentPredictionDto,
    GeneratePredictionCommand,
    GenerationSummary,
)


class AiPredictionUseCase(ABC):
    """AI 승부예측 입력 포트.

    **조회와 생성이 갈려 있는 것이 이 포트의 요점이다.** 조회는 저장된 값을 읽기만
    하고, 생성은 관리자·배치만 부른다. 한 메서드로 합치면 사용자가 페이지를 열
    때마다 LLM이 도는 구조가 되어 비용이 트래픽에 비례한다(하네스 §2-D7·§3-D1).
    """

    @abstractmethod
    async def list_predictions(self, *, event_slug: str) -> list[AgentPredictionDto]:
        """저장된 예측을 돌려준다. **LLM을 부르지 않는다.**

        예측이 없으면 빈 목록이다 — 없는 것은 실패가 아니다.
        """

    @abstractmethod
    async def generate(self, command: GeneratePredictionCommand) -> GenerationSummary:
        """에이전트를 돌려 예측을 만들고 저장한다.

        경기 하나가 실패해도 나머지는 계속 만든다 — 실패 건수는 요약에 담는다.
        없는 이벤트·경기면 `MatchNotFoundError`를 던진다.
        """
