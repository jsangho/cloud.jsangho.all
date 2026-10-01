"""사용자 관리 — 권한 변경의 잠금장치와 엔드포인트 계약.

**관리자를 모두 떼면 되돌릴 방법이 없다** — 이 기능이 없애려고 만든 그 상태(DB를
손으로 고치는 것)로 되돌아간다. 그래서 잠금장치 둘을 테스트가 붙든다.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from auth.adapter.inbound.api.user_admin_router import user_admin_router
from auth.app.use_cases.user_admin_interactor import UserAdminInteractor
from auth.dependencies.auth_provider import get_user_admin_use_case
from core.entities.user_model import UserModel
from core.security.dependencies import get_current_user
from core.security.role import UserRole
from core.security.token_verifier import TokenPayload


def _user(
    user_id: int, nickname: str, role: str, *, email: str | None = None
) -> UserModel:
    user = UserModel()
    user.id = user_id
    user.login_id = f"login{user_id}"
    user.nickname = nickname
    user.email = email
    user.password_hash = "hash-must-not-leak"
    user.role = role
    user.oauth_provider = None
    user.oauth_id = None
    return user


class FakeRepository:
    def __init__(self, users: list[UserModel]) -> None:
        self._users = users
        self.writes: list[tuple[int, str]] = []

    async def list_users(self, *, query: str | None = None, limit: int = 100):
        found = [
            u
            for u in self._users
            if query is None or query.lower() in u.nickname.lower()
        ]
        return tuple(found[:limit])

    async def find_by_id(self, *, user_id: int):
        return next((u for u in self._users if u.id == user_id), None)

    async def count_by_role(self, *, role: str) -> int:
        return sum(1 for u in self._users if u.role == role)

    async def set_role(self, *, user_id: int, role: str) -> bool:
        target = next((u for u in self._users if u.id == user_id), None)
        if target is None:
            return False
        self.writes.append((user_id, role))
        target.role = role
        return True


# ── 유스케이스 ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_promote_writes_once() -> None:
    repository = FakeRepository([_user(1, "owner", "admin"), _user(2, "fan", "user")])

    changed = await UserAdminInteractor(repository).change_role(
        user_id=2, role=UserRole.ADMIN, actor_id=1
    )

    assert repository.writes == [(2, "admin")]
    assert changed.role == "admin"


@pytest.mark.asyncio
async def test_same_role_writes_nothing() -> None:
    """멱등. 아무 일도 안 일어난 변경이 기록에 쌓이면 기록이 거짓말을 시작한다."""
    repository = FakeRepository([_user(1, "owner", "admin"), _user(2, "fan", "user")])

    await UserAdminInteractor(repository).change_role(
        user_id=2, role=UserRole.USER, actor_id=1
    )

    assert repository.writes == []


@pytest.mark.asyncio
async def test_cannot_demote_yourself() -> None:
    """다른 관리자가 있어도 막는다 — 실수로 스스로를 잠그는 경로를 없앤다."""
    repository = FakeRepository(
        [_user(1, "owner", "admin"), _user(2, "second", "admin")]
    )

    with pytest.raises(HTTPException) as caught:
        await UserAdminInteractor(repository).change_role(
            user_id=1, role=UserRole.USER, actor_id=1
        )

    assert caught.value.status_code == 409
    assert repository.writes == []


@pytest.mark.asyncio
async def test_cannot_demote_the_last_admin() -> None:
    repository = FakeRepository([_user(1, "owner", "admin"), _user(2, "fan", "user")])

    with pytest.raises(HTTPException) as caught:
        await UserAdminInteractor(repository).change_role(
            user_id=1, role=UserRole.USER, actor_id=2
        )

    assert caught.value.status_code == 409
    assert repository.writes == []


@pytest.mark.asyncio
async def test_second_admin_can_be_demoted() -> None:
    """관리자가 둘일 때 하나를 떼는 것은 막지 않는다."""
    repository = FakeRepository(
        [_user(1, "owner", "admin"), _user(2, "second", "admin")]
    )

    await UserAdminInteractor(repository).change_role(
        user_id=2, role=UserRole.USER, actor_id=1
    )

    assert repository.writes == [(2, "user")]


@pytest.mark.asyncio
async def test_missing_user_is_404() -> None:
    repository = FakeRepository([_user(1, "owner", "admin")])

    with pytest.raises(HTTPException) as caught:
        await UserAdminInteractor(repository).change_role(
            user_id=99, role=UserRole.ADMIN, actor_id=1
        )

    assert caught.value.status_code == 404


@pytest.mark.asyncio
async def test_limit_is_bounded_in_the_use_case() -> None:
    """라우터가 아닌 곳에서 불려도 상한이 산다."""
    captured: list[int] = []

    class Spy(FakeRepository):
        async def list_users(self, *, query=None, limit=100):
            captured.append(limit)
            return ()

    await UserAdminInteractor(Spy([])).list_users(limit=10_000)

    assert captured == [500]


# ── 엔드포인트 ────────────────────────────────────────────────────────────────


class FakeUseCase:
    def __init__(
        self, users: list[UserModel], *, page: list[UserModel] | None = None
    ) -> None:
        self._users = users
        #: 목록이 검색·상한으로 잘린 경우. 비우면 전체가 그대로 한 쪽이다.
        self._page = page if page is not None else users
        self.changes: list[tuple[int, str, int]] = []

    async def list_users(self, *, query: str | None = None, limit: int = 100):
        return tuple(self._page)

    async def count_admins(self) -> int:
        return sum(1 for u in self._users if u.role == UserRole.ADMIN.value)

    async def change_role(self, *, user_id: int, role: UserRole, actor_id: int):
        self.changes.append((user_id, role.value, actor_id))
        target = next(u for u in self._users if u.id == user_id)
        target.role = role.value
        return target


def _claims(roles: list[str], *, sub: str = "1") -> TokenPayload:
    return TokenPayload(
        sub=sub,
        aud="jsangho-api",
        exp=9999999999,
        iat=0,
        jti="jti",
        roles=roles,
        platform="web",
        device_id="d1",
    )


def _client(use_case: FakeUseCase, *, roles: list[str] | None = None) -> TestClient:
    app = FastAPI()
    app.include_router(user_admin_router, prefix="/auth")
    app.dependency_overrides[get_user_admin_use_case] = lambda: use_case
    if roles is not None:
        app.dependency_overrides[get_current_user] = lambda: _claims(roles)
    return TestClient(app)


def _fixture() -> FakeUseCase:
    return FakeUseCase(
        [_user(1, "owner", "admin"), _user(2, "fan", "user", email="f@x.io")]
    )


def test_list_rejects_anonymous_callers() -> None:
    assert _client(_fixture()).get("/auth/admin/users").status_code == 401


def test_list_rejects_non_admin_users() -> None:
    assert (
        _client(_fixture(), roles=["user"]).get("/auth/admin/users").status_code == 403
    )


def test_role_change_rejects_non_admin_users() -> None:
    use_case = _fixture()

    response = _client(use_case, roles=["user"]).patch(
        "/auth/admin/users/2/role", json={"role": "admin"}
    )

    assert response.status_code == 403
    assert use_case.changes == []


def test_list_counts_admins_and_hides_secrets() -> None:
    response = _client(_fixture(), roles=["admin"]).get("/auth/admin/users")

    assert response.status_code == 200
    body = response.json()
    assert body["admins"] == 1
    assert body["items"][1] == {
        "userId": 2,
        "loginId": "login2",
        "nickname": "fan",
        "email": "f@x.io",
        "role": "user",
        "oauthProvider": None,
    }
    # 비밀번호 해시는 응답 어디에도 없다.
    assert "hash-must-not-leak" not in response.text
    assert "password" not in response.text


def test_admin_count_is_global_not_page_local() -> None:
    """검색으로 잘린 목록에서 세면 화면이 **거짓으로 잠근다**.

    관리자가 셋인데 검색 결과에 하나만 걸리면, 목록에서 센 값은 1이고 화면은
    "마지막 관리자입니다"로 버튼을 막는다 — 서버는 허용하는 변경이다.
    """
    admins = [_user(i, f"admin{i}", "admin") for i in (1, 2, 3)]
    use_case = FakeUseCase(admins, page=[admins[0]])

    body = _client(use_case, roles=["admin"]).get("/auth/admin/users?q=admin1").json()

    assert len(body["items"]) == 1
    assert body["admins"] == 3


def test_role_change_passes_the_actor_through() -> None:
    """누가 바꿨는지는 토큰에서 온다 — 본문으로 받으면 사칭할 수 있다."""
    use_case = _fixture()

    response = _client(use_case, roles=["admin"]).patch(
        "/auth/admin/users/2/role", json={"role": "admin"}
    )

    assert response.status_code == 200
    assert use_case.changes == [(2, "admin", 1)]
    assert response.json()["role"] == "admin"


def test_unknown_role_is_422() -> None:
    use_case = _fixture()

    response = _client(use_case, roles=["admin"]).patch(
        "/auth/admin/users/2/role", json={"role": "superuser"}
    )

    assert response.status_code == 422
    assert use_case.changes == []
