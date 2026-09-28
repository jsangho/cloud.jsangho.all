from __future__ import annotations

from abc import ABC, abstractmethod

from kayfabe.app.dtos.result_verification_dto import (
    VerificationRun,
    VerifyResultsCommand,
)


class ResultVerificationUseCase(ABC):
    """결과 미기록 경기의 승자를 위키에서 찾아 확정하는 입력 포트."""

    @abstractmethod
    async def verify(self, command: VerifyResultsCommand) -> VerificationRun: ...
