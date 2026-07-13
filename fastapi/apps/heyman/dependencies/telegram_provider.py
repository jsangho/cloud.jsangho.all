from heyman.adapter.outbound.repositories.telegram_repository import (
    TelegramPgRepository,
)
from heyman.app.ports.input.telegram_use_case import TelegramUseCase
from heyman.app.use_cases.telegram_interactor import TelegramInteractor


def get_telegram_use_case() -> TelegramUseCase:
    return TelegramInteractor(repository=TelegramPgRepository())
