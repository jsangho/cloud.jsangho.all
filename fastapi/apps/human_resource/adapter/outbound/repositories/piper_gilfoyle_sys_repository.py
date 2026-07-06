from sqlalchemy.ext.asyncio import AsyncSession

from human_resource.app.dtos.piper_gilfoyle_sys_dto import (
    GilfoyleSysQuery,
    GilfoyleSysResponse,
)
from human_resource.app.ports.output.piper_gilfoyle_sys_port import GilfoyleSysPort


class GilfoyleSysRepository(GilfoyleSysPort):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def introduce_myself(self, query: GilfoyleSysQuery) -> GilfoyleSysResponse:
        return GilfoyleSysResponse(id=query.id, name=query.name)
