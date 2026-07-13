from __future__ import annotations

from heyman.app.dtos.watcher_dto import WatcherQuery, WatcherResponse
from heyman.app.ports.output.watcher_repository import WatcherRepository
from sqlalchemy.ext.asyncio import AsyncSession


class WatcherPgRepository(WatcherRepository):
    """Neon(Postgres) Watson(Watcher Hub) 어댑터."""

    def __init__(self, session: AsyncSession | None = None) -> None:
        self._session = session

    async def introduce_myself(self, query: WatcherQuery) -> WatcherResponse:
        return WatcherResponse(
            id=query.id,
            name=query.name,
            description="Gmail/Telegram/Discord 인바운드 이벤트를 감시하고 1차 분류(Triage)하는 관문입니다.",
        )
