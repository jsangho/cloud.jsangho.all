from admin.app.dtos.piper_dinesh_dash_dto import (
    DineshDashQuery,
    DineshDashResponse,
)
from admin.app.ports.output.piper_dinesh_dash_port import DineshDashPort
from sqlalchemy.ext.asyncio import AsyncSession


class DineshDashRepository(DineshDashPort):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def introduce_myself(self, query: DineshDashQuery) -> DineshDashResponse:
        return DineshDashResponse(id=query.id, name=query.name)
