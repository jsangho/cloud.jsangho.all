from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from manager.app.dtos.discord_dto import DiscordQuery, DiscordResponse
from manager.app.ports.output.discord_repository import DiscordRepository


class DiscordPgRepository(DiscordRepository):
    """Neon(Postgres) Discord 메시지 로그 어댑터."""

    def __init__(self, session: AsyncSession | None = None) -> None:
        self._session = session

    async def introduce_myself(self, query: DiscordQuery) -> DiscordResponse:
        return DiscordResponse(
            id=query.id,
            name=query.name,
            description="Discord 채널에 알림·보고서를 전송하는 봇 서비스입니다.",
        )
