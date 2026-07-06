from __future__ import annotations

from abc import ABC, abstractmethod

from human_resource.app.dtos.piper_dunn_coo_dto import DunnCooQuery, DunnCooResponse


class DunnCooPort(ABC):
    @abstractmethod
    async def introduce_myself(self, query: DunnCooQuery) -> DunnCooResponse:
        pass
