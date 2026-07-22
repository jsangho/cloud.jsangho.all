from __future__ import annotations

import asyncio

from core.entities.user_model import UserModel
from core.security.password import verify_password

from auth.app.ports.input.login_use_case import LoginUseCase
from auth.app.ports.output.user_repository import UserRepository
from fastapi import HTTPException


class LoginInteractor(LoginUseCase):
    """로그인 유스케이스 구현체."""

    def __init__(self, repository: UserRepository) -> None:
        self._repository = repository

    async def login_user(self, *, login_id: str, password: str) -> UserModel:
        user = await self._repository.find_by_login_id(login_id=login_id)
        password_ok = await asyncio.to_thread(
            verify_password, password, user.password_hash if user else ""
        )
        if user is None or not password_ok:
            raise HTTPException(
                status_code=401,
                detail="ID 또는 비밀번호가 올바르지 않습니다.",
            )
        return user
