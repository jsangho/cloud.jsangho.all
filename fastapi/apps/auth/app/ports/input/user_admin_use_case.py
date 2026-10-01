from __future__ import annotations

from abc import ABC, abstractmethod

from core.entities.user_model import UserModel
from core.security.role import UserRole


class UserAdminUseCase(ABC):
    """사용자 목록과 역할 변경.

    **지금까지 역할을 주는 경로가 코드에 아예 없었다.** 회원가입은 늘
    `UserRole.USER`로 만들고(`signup_router`), 저장소 전체에서 `"admin"`을 쓰는 코드는
    enum 정의뿐이었다 — 기존 관리자 계정은 사람이 DB를 직접 고쳐 만든 것이다. 그래서
    둘째 관리자가 필요해지는 날 또 SQL을 쳐야 했다.
    """

    @abstractmethod
    async def list_users(
        self, *, query: str | None = None, limit: int = 100
    ) -> tuple[UserModel, ...]: ...

    @abstractmethod
    async def count_admins(self) -> int:
        """**전체** 관리자 수. 목록과 따로 세는 이유가 있다.

        목록은 검색과 상한으로 잘린다. 잘린 목록에서 센 값으로 "마지막 관리자"를
        판단하면, 관리자가 셋인데 검색에 하나만 걸린 화면이 **서버가 허용하는 변경을
        거짓 이유로 막는다**.
        """
        ...

    @abstractmethod
    async def change_role(
        self, *, user_id: int, role: UserRole, actor_id: int
    ) -> UserModel:
        """역할을 바꾸고 바뀐 사용자를 돌려준다.

        `actor_id`를 받는 이유는 둘이다 — 로그에 **누가 바꿨는지** 남기고, 자기
        권한을 스스로 떼는 것을 막는다.
        """
        ...
