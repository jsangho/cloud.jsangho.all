from __future__ import annotations

from abc import ABC, abstractmethod

from superstar.domain.entities.user_model import UserModel


class MurderListUseCase(ABC):
    """`/user/murder-list/*` inbound(murder_list_router)가 호출하는 입력 포트 (구현·로그 없음, ABC만)."""

    @abstractmethod
    async def get_user_by_id(self, *, user_id: int) -> UserModel:
        """회원 프로필 조회 (`GET /users/{user_id}`)."""
        ...
