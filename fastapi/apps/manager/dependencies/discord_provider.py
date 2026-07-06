from manager.adapter.outbound.repositories.discord_repository import DiscordPgRepository
from manager.app.ports.input.discord_use_case import DiscordUseCase
from manager.app.use_cases.discord_interactor import DiscordInteractor


def get_discord_use_case() -> DiscordUseCase:
    return DiscordInteractor(repository=DiscordPgRepository())
