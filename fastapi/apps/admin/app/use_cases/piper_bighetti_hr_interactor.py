from __future__ import annotations

from admin.app.dtos.piper_bighetti_hr_dto import (
    BighettiHrQuery,
    BighettiHrResponse,
)
from admin.app.ports.input.piper_bighetti_hr_use_case import BighettiHrUseCase
from admin.app.ports.output.piper_bighetti_hr_port import BighettiHrPort


class BighettiHrInteractor(BighettiHrUseCase):
    def __init__(self, repository: BighettiHrPort):
        self.repository = repository

    async def introduce_myself(self, query: BighettiHrQuery) -> BighettiHrResponse:
        return await self.repository.introduce_myself(query)
