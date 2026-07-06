from __future__ import annotations

from abc import ABC, abstractmethod

from manager.app.dtos.discord_dto import DiscordQuery, DiscordResponse


class DiscordRepository(ABC):
    @abstractmethod
    async def introduce_myself(self, query: DiscordQuery) -> DiscordResponse: ...
