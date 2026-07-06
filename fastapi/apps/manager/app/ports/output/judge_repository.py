from __future__ import annotations

from abc import ABC, abstractmethod

from manager.app.dtos.judge_dto import JudgeQuery, JudgeResponse


class JudgeRepository(ABC):
    @abstractmethod
    async def introduce_myself(self, query: JudgeQuery) -> JudgeResponse: ...
