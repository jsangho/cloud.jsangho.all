from sqlalchemy.ext.asyncio import AsyncSession

from human_resource.app.dtos.piper_hendricks_ceo_dto import (
    HendricksCeoQuery,
    HendricksCeoResponse,
)
from human_resource.app.ports.output.piper_hendricks_ceo_port import HendricksCeoPort


class HendricksCeoRepository(HendricksCeoPort):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def introduce_myself(self, query: HendricksCeoQuery) -> HendricksCeoResponse:
        return HendricksCeoResponse(id=query.id, name=query.name)
