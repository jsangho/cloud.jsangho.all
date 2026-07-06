from __future__ import annotations

from abc import ABC, abstractmethod

from manager.app.dtos.judge_dto import JudgeQuery, JudgeResponse


class JudgeUseCase(ABC):
    """`/manager/judge/*` inbound 입력 포트."""

    @abstractmethod
    async def introduce_myself(self, query: JudgeQuery) -> JudgeResponse:
        """Judge 자기소개."""
        ...
