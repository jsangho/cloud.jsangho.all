from __future__ import annotations

from abc import ABC, abstractmethod

from heyman.app.dtos.watcher_dto import WatcherQuery, WatcherResponse


class WatcherRepository(ABC):
    @abstractmethod
    async def introduce_myself(self, query: WatcherQuery) -> WatcherResponse: ...
