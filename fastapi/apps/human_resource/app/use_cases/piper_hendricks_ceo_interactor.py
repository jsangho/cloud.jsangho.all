from __future__ import annotations

from human_resource.app.dtos.piper_hendricks_ceo_dto import (
    HendricksCeoQuery,
    HendricksCeoResponse,
)
from human_resource.app.ports.input.piper_hendricks_ceo_use_case import (
    HendricksCeoUseCase,
)
from human_resource.app.ports.output.piper_hendricks_ceo_port import HendricksCeoPort


class HendricksCeoInteractor(HendricksCeoUseCase):
    def __init__(self, repository: HendricksCeoPort):
        self.repository = repository

    async def introduce_myself(self, query: HendricksCeoQuery) -> HendricksCeoResponse:
        return await self.repository.introduce_myself(query)
