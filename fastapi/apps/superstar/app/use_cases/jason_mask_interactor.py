from __future__ import annotations

from fastapi import HTTPException
from superstar.app.ports.input.jason_mask import JasonMaskUseCase
from superstar.app.ports.input.jason_mask_schema import JasonMaskSchema
from superstar.app.ports.output.jason_mask_repository import JasonMaskRepository
from superstar.domain.services.password import hash_password


class JasonMaskInteractor(JasonMaskUseCase):
    """회원가입 유스케이스 구현체."""

    def __init__(self, repository: JasonMaskRepository) -> None:
        self._repository = repository

    async def save_user(self, *, user_schema: JasonMaskSchema) -> None:
        if user_schema.password != user_schema.password_confirm:
            raise HTTPException(
                status_code=400,
                detail="비밀번호와 비밀번호 확인이 일치하지 않습니다.",
            )

        if await self._repository.find_by_email(user_schema.email):
            raise HTTPException(status_code=409, detail="이미 가입된 이메일입니다.")

        if await self._repository.find_by_login_id(user_schema.login_id):
            raise HTTPException(status_code=409, detail="이미 사용 중인 ID입니다.")

        password_hash = hash_password(user_schema.password)
        await self._repository.save_user(user_schema, password_hash)
