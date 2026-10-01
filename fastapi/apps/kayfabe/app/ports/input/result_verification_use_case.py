from __future__ import annotations

from abc import ABC, abstractmethod

from kayfabe.app.dtos.result_verification_dto import (
    VerificationRun,
    VerifyResultsCommand,
)
from kayfabe.domain.entities.result_verification import MatchUnderReview


class ResultVerificationUseCase(ABC):
    """결과 미기록 경기의 승자를 위키에서 찾아 확정하는 입력 포트."""

    @abstractmethod
    async def list_pending(
        self, *, event_slug: str | None = None
    ) -> tuple[MatchUnderReview, ...]:
        """무엇을 볼 것인지만 돌려준다. **모델을 부르지 않는다.**

        `verify`가 비용이 드는 유일한 메소드이고, 그 비용을 사람이 누르기 전에 세어
        보려면 대상 목록이 공짜여야 한다. 돌려주는 것은 `verify`가 실제로 고르는
        것과 **같은 목록**이다(같은 리포지토리·같은 순서) — 따로 세면 화면이 보여준
        것과 돌아간 것이 갈린다.
        """
        ...

    @abstractmethod
    async def verify(self, command: VerifyResultsCommand) -> VerificationRun: ...
