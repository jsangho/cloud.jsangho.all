from __future__ import annotations

from core.entities.user_model import UserModel

from auth.app.ports.input.profile_use_case import ProfileUseCase
from auth.app.ports.output.user_repository import UserRepository
from fastapi import HTTPException


class ProfileInteractor(ProfileUseCase):
    """프로필 조회 유스케이스 구현체."""

    def __init__(self, repository: UserRepository) -> None:
        self._repository = repository

    async def get_user_by_id(self, *, user_id: int) -> UserModel:
        user = await self._repository.find_by_id(user_id=user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="유저를 찾을 수 없습니다.")
        return user
