from __future__ import annotations

from heyman.app.dtos.judge_dto import JudgeQuery, JudgeResponse
from heyman.app.ports.input.judge_use_case import JudgeUseCase
from heyman.app.ports.output.judge_repository import JudgeRepository


class JudgeInteractor(JudgeUseCase):
    def __init__(self, repository: JudgeRepository) -> None:
        self._repository = repository

    async def introduce_myself(self, query: JudgeQuery) -> JudgeResponse:
        return await self._repository.introduce_myself(query)
