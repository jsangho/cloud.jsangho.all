from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from titanic.app.dtos.crew_hartley_violin_dto import (
    HartleyViolinQuery,
    HartleyViolinResponse,
)
from titanic.app.ports.output.crew_hartley_violin_port import HartleyViolinPort


class HartleyViolinRepository(HartleyViolinPort):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def introduce_myself(
        self, query: HartleyViolinQuery
    ) -> HartleyViolinResponse:
        return HartleyViolinResponse(
            id=query.id * 10000,
            name=query.name + "가 레포지토리에 다녀옴",
        )
