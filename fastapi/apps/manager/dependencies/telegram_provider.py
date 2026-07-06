from manager.adapter.outbound.repositories.telegram_repository import (
    TelegramPgRepository,
)
from manager.app.ports.input.telegram_use_case import TelegramUseCase
from manager.app.use_cases.telegram_interactor import TelegramInteractor


def get_telegram_use_case() -> TelegramUseCase:
    return TelegramInteractor(repository=TelegramPgRepository())
