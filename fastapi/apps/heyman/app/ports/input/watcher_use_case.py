from __future__ import annotations

from abc import ABC, abstractmethod

from heyman.app.dtos.receiver_dto import ReceiverCommand
from heyman.app.dtos.watcher_dto import (
    WatcherFilterResult,
    WatcherQuery,
    WatcherResponse,
)


class WatcherUseCase(ABC):
    """`/manager/watcher/*` inbound 입력 포트."""

    @abstractmethod
    async def introduce_myself(self, query: WatcherQuery) -> WatcherResponse:
        """Watson(Watcher Hub) 자기소개."""
        ...

    @abstractmethod
    async def filter_and_forward(self, cmd: ReceiverCommand) -> WatcherFilterResult:
        """KcELECTRA로 메일을 1차 필터링하고, 정상(ham) 메일만 pgvector 파이프라인으로 전달한다."""
        ...
