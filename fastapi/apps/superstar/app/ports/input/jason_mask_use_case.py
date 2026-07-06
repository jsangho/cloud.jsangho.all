from __future__ import annotations

from abc import ABC, abstractmethod

from superstar.app.ports.input.jason_mask_schema import JasonMaskSchema


class JasonMaskUseCase(ABC):
    """`/user/jason-mask/signup` inbound(jason_mask_router)가 호출하는 입력 포트 (구현·로그 없음, ABC만)."""

    @abstractmethod
    async def save_user(self, *, user_schema: JasonMaskSchema) -> None:
        """회원가입 (`POST /signup`)."""
        ...
