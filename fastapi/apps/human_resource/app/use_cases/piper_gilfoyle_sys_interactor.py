from __future__ import annotations

from human_resource.app.dtos.piper_gilfoyle_sys_dto import (
    GilfoyleSysQuery,
    GilfoyleSysResponse,
)
from human_resource.app.ports.input.piper_gilfoyle_sys_use_case import (
    GilfoyleSysUseCase,
)
from human_resource.app.ports.output.piper_gilfoyle_sys_port import GilfoyleSysPort


class GilfoyleSysInteractor(GilfoyleSysUseCase):
    def __init__(self, repository: GilfoyleSysPort):
        self.repository = repository

    async def introduce_myself(self, query: GilfoyleSysQuery) -> GilfoyleSysResponse:
        return await self.repository.introduce_myself(query)
