"""사용자 관리 유스케이스.

권한을 바꾸는 일은 **되돌리기 어려운 쪽으로 틀릴 수 있다** — 관리자를 모두 떼면
아무도 다시 붙일 수 없고, 그때는 DB를 손으로 고치는 수밖에 없다(그걸 없애려고 만든
기능이다). 그래서 잠금장치 둘을 둔다.

1. **자기 자신의 관리자 권한을 떼지 못한다.** 다른 관리자에게 부탁하면 되므로 잃는
   것이 없고, 실수로 스스로를 잠그는 경로가 사라진다.
2. **마지막 관리자를 떼지 못한다.** 관리자가 둘일 때 하나를 떼는 것은 막지 않는다.

변경은 **로그에 남는다**(누가·누구를·무엇에서 무엇으로). 같은 역할로 바꾸는 요청은
쓰지 않는다 — 아무 일도 안 일어난 변경이 기록에 쌓이면 기록이 거짓말을 시작한다.
"""

from __future__ import annotations

import logging

from fastapi import HTTPException

from auth.app.ports.input.user_admin_use_case import UserAdminUseCase
from auth.app.ports.output.user_admin_repository import UserAdminRepository
from core.entities.user_model import UserModel
from core.security.role import UserRole

logger = logging.getLogger("uvicorn.error")

#: 목록 상한. 지금 사용자가 몇 명이든, 열린 상한은 그 자체로 사고다.
MAX_LIST_LIMIT = 500


class UserAdminInteractor(UserAdminUseCase):
    def __init__(self, repository: UserAdminRepository) -> None:
        self._repository = repository

    async def list_users(
        self, *, query: str | None = None, limit: int = 100
    ) -> tuple[UserModel, ...]:
        bounded = max(1, min(limit, MAX_LIST_LIMIT))
        return await self._repository.list_users(query=query, limit=bounded)

    async def count_admins(self) -> int:
        return await self._repository.count_by_role(role=UserRole.ADMIN.value)

    async def change_role(
        self, *, user_id: int, role: UserRole, actor_id: int
    ) -> UserModel:
        target = await self._repository.find_by_id(user_id=user_id)
        if target is None:
            raise HTTPException(status_code=404, detail="유저를 찾을 수 없습니다.")

        if target.role == role.value:
            # 멱등. 쓰지 않고 지금 상태를 그대로 돌려준다.
            return target

        if target.role == UserRole.ADMIN.value:
            if target.id == actor_id:
                raise HTTPException(
                    status_code=409,
                    detail="자신의 관리자 권한은 뗄 수 없습니다. 다른 관리자에게 요청하세요.",
                )
            if await self._repository.count_by_role(role=UserRole.ADMIN.value) <= 1:
                raise HTTPException(
                    status_code=409,
                    detail="마지막 관리자입니다. 먼저 다른 관리자를 지정하세요.",
                )

        if not await self._repository.set_role(user_id=user_id, role=role.value):
            # 방금 읽은 행이 쓰기에서 0행이면 그 사이에 사라진 것이다.
            raise HTTPException(
                status_code=409, detail="대상이 바뀌었습니다. 다시 시도해 주세요."
            )

        logger.info(
            "[auth.user_admin] 역할 변경 | actor=%s target=%s %s -> %s",
            actor_id,
            user_id,
            target.role,
            role.value,
        )
        changed = await self._repository.find_by_id(user_id=user_id)
        if changed is None:
            raise HTTPException(
                status_code=409, detail="대상이 바뀌었습니다. 다시 시도해 주세요."
            )
        return changed
