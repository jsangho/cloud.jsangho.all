from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from kayfabe.app.dtos.agent_prediction_dto import MatchContext
from kayfabe.domain.entities.agent_prediction import AgentPrediction


class MatchNotFoundError(Exception):
    """이벤트나 경기가 없다. 클라이언트에는 404."""


class AgentPredictionRepository(ABC):
    """예측 저장·조회 + 예측에 필요한 경기 정보 읽기."""

    @abstractmethod
    async def list_by_event(self, *, event_slug: str) -> list[AgentPrediction]:
        """저장된 예측. 없으면 빈 목록."""

    @abstractmethod
    async def load_contexts(
        self, *, event_slug: str, match_keys: Sequence[str]
    ) -> list[MatchContext]:
        """카드에서 에이전트가 볼 경기 정보를 뽑는다.

        `match_keys`가 비면 그 이벤트 전부. 이벤트가 없으면 `MatchNotFoundError`,
        지정한 키가 없으면 그 키만 빠진 목록을 돌려준다.
        """

    @abstractmethod
    async def existing_match_keys(self, *, event_slug: str) -> set[str]:
        """이미 예측이 있는 경기 키 — `force`가 아닐 때 건너뛸 대상."""

    @abstractmethod
    async def save(self, prediction: AgentPrediction) -> None:
        """예측과 리포트를 함께 저장한다. 같은 경기의 기존 예측은 대체한다."""
