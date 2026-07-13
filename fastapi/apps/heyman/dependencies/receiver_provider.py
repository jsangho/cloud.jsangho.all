from __future__ import annotations

from heyman.adapter.outbound.repositories.receiver_repository import (
    ReceiverPgRepository,
)
from heyman.app.ports.input.receiver_use_case import ReceiverUseCase
from heyman.app.use_cases.receiver_interactor import ReceiverInteractor
from heyman.dependencies.watcher_provider import get_watcher_use_case


def get_receiver_use_case() -> ReceiverUseCase:
    return ReceiverInteractor(ReceiverPgRepository(), get_watcher_use_case())
