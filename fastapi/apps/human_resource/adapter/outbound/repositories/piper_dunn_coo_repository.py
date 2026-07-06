from sqlalchemy.ext.asyncio import AsyncSession

from human_resource.app.dtos.piper_dunn_coo_dto import DunnCooQuery, DunnCooResponse
from human_resource.app.ports.output.piper_dunn_coo_port import DunnCooPort


class DunnCooRepository(DunnCooPort):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def introduce_myself(self, query: DunnCooQuery) -> DunnCooResponse:
        return DunnCooResponse(id=query.id, name=query.name)
