from __future__ import annotations

from manager.app.dtos.discord_dto import DiscordQuery, DiscordResponse
from manager.app.ports.input.discord_use_case import DiscordUseCase
from manager.app.ports.output.discord_repository import DiscordRepository


class DiscordInteractor(DiscordUseCase):
    def __init__(self, repository: DiscordRepository) -> None:
        self._repository = repository

    async def introduce_myself(self, query: DiscordQuery) -> DiscordResponse:
        return await self._repository.introduce_myself(query)
