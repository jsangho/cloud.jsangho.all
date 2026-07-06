from __future__ import annotations

from manager.app.dtos.judge_dto import JudgeQuery, JudgeResponse
from manager.app.ports.input.judge_use_case import JudgeUseCase
from manager.app.ports.output.judge_repository import JudgeRepository


class JudgeInteractor(JudgeUseCase):
    def __init__(self, repository: JudgeRepository) -> None:
        self._repository = repository

    async def introduce_myself(self, query: JudgeQuery) -> JudgeResponse:
        return await self._repository.introduce_myself(query)
