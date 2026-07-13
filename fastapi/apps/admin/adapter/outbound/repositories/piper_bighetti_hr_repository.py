from admin.app.dtos.piper_bighetti_hr_dto import (
    BighettiHrQuery,
    BighettiHrResponse,
)
from admin.app.ports.output.piper_bighetti_hr_port import BighettiHrPort
from sqlalchemy.ext.asyncio import AsyncSession


class BighettiHrRepository(BighettiHrPort):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def introduce_myself(self, query: BighettiHrQuery) -> BighettiHrResponse:
        return BighettiHrResponse(id=query.id, name=query.name)
