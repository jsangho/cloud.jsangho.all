from __future__ import annotations

from manager.adapter.outbound.repositories.receiver_repository import (
    ReceiverPgRepository,
)
from manager.app.ports.input.receiver_use_case import ReceiverUseCase
from manager.app.use_cases.receiver_interactor import ReceiverInteractor
from manager.dependencies.watcher_provider import get_watcher_use_case


def get_receiver_use_case() -> ReceiverUseCase:
    return ReceiverInteractor(ReceiverPgRepository(), get_watcher_use_case())
