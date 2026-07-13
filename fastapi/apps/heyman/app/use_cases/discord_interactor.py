from __future__ import annotations

from heyman.app.dtos.discord_dto import DiscordQuery, DiscordResponse
from heyman.app.ports.input.discord_use_case import DiscordUseCase
from heyman.app.ports.output.discord_repository import DiscordRepository


class DiscordInteractor(DiscordUseCase):
    def __init__(self, repository: DiscordRepository) -> None:
        self._repository = repository

    async def introduce_myself(self, query: DiscordQuery) -> DiscordResponse:
        return await self._repository.introduce_myself(query)
