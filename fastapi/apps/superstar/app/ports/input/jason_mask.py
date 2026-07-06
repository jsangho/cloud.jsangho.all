from __future__ import annotations

from abc import ABC, abstractmethod

from superstar.app.ports.input.jason_mask_schema import JasonMaskSchema


class JasonMaskUseCase(ABC):
    @abstractmethod
    async def save_user(self, *, user_schema: JasonMaskSchema) -> None: ...
