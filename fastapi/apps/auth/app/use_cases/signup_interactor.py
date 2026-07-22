from __future__ import annotations

import asyncio

from core.security.password import hash_password
from core.security.role import UserRole

from auth.app.ports.input.signup_use_case import SignupUseCase
from auth.app.ports.output.user_repository import UserRepository
from fastapi import HTTPException


class SignupInteractor(SignupUseCase):
    """회원가입 유스케이스 구현체."""

    def __init__(self, repository: UserRepository) -> None:
        self._repository = repository

    async def signup(
        self,
        *,
        login_id: str,
        nickname: str,
        email: str,
        password: str,
        password_confirm: str,
    ) -> None:
        if password != password_confirm:
            raise HTTPException(
                status_code=400, detail="비밀번호와 비밀번호 확인이 일치하지 않습니다."
            )
        if await self._repository.find_by_email(email=email):
            raise HTTPException(status_code=409, detail="이미 가입된 이메일입니다.")
        if await self._repository.find_by_login_id(login_id=login_id):
            raise HTTPException(status_code=409, detail="이미 사용 중인 ID입니다.")
        password_hash = await asyncio.to_thread(hash_password, password)
        await self._repository.create_user(
            login_id=login_id,
            nickname=nickname,
            email=email,
            password_hash=password_hash,
            role=UserRole.USER.value,
        )
