from __future__ import annotations

from fastapi import HTTPException
from superstar.app.ports.input.murder_list import MurderListUseCase
from superstar.app.ports.output.murder_list_repository import MurderListRepository
from superstar.domain.entities.user_model import UserModel


class MurderListInteractor(MurderListUseCase):
    """유저 프로필 조회 유스케이스 구현체."""

    def __init__(self, repository: MurderListRepository) -> None:
        self._repository = repository

    async def get_user_by_id(self, *, user_id: int) -> UserModel:
        user = await self._repository.find_by_id(user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="유저를 찾을 수 없습니다.")
        return user
