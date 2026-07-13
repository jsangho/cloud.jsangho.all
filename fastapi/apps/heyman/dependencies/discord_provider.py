from heyman.adapter.outbound.repositories.discord_repository import DiscordPgRepository
from heyman.app.ports.input.discord_use_case import DiscordUseCase
from heyman.app.use_cases.discord_interactor import DiscordInteractor


def get_discord_use_case() -> DiscordUseCase:
    return DiscordInteractor(repository=DiscordPgRepository())
