from __future__ import annotations

from abc import ABC, abstractmethod

from manager.app.dtos.discord_dto import DiscordQuery, DiscordResponse


class DiscordUseCase(ABC):
    """`/manager/discord/*` inbound 입력 포트."""

    @abstractmethod
    async def introduce_myself(self, query: DiscordQuery) -> DiscordResponse:
        """Discord 서비스 자기소개."""
        ...
