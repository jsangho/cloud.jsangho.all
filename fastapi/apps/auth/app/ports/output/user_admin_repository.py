from __future__ import annotations

from abc import ABC, abstractmethod

from core.entities.user_model import UserModel


class UserAdminRepository(ABC):
    """사용자 목록·역할 쓰기만 여는 좁은 포트.

    인증이 쓰는 `UserRepository`(조회 넷 + 생성 셋)에 얹지 않는다. 그쪽은 **로그인
    경로**가 쥐는 면이고, 거기에 역할 쓰기가 생기면 로그인 흐름이 권한을 바꿀 수 있는
    자리에 서게 된다. 구현은 같은 PG 어댑터가 겸한다.
    """

    @abstractmethod
    async def list_users(
        self, *, query: str | None = None, limit: int = 100
    ) -> tuple[UserModel, ...]:
        """`id` 순서로. `query`는 닉네임·로그인 아이디·이메일 부분 일치."""
        ...

    @abstractmethod
    async def find_by_id(self, *, user_id: int) -> UserModel | None:
        """대상 한 명. `UserRepository`에도 같은 이름이 있고 **구현은 하나**다 —
        포트가 좁은 것은 쥐는 쪽이 할 수 있는 일을 줄이기 위한 것이고, 어댑터를
        쪼개려는 것이 아니다.
        """
        ...

    @abstractmethod
    async def count_by_role(self, *, role: str) -> int:
        """그 역할을 가진 사용자 수. **마지막 관리자를 떼지 못하게** 하는 근거다."""
        ...

    @abstractmethod
    async def set_role(self, *, user_id: int, role: str) -> bool:
        """`role` 한 칸만 쓴다. 대상 행이 없으면 `False`."""
        ...
