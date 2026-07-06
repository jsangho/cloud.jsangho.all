from __future__ import annotations

from superstar.domain.value_objects.role import UserRole


def format_preview_signup(
    layer: int,
    *,
    login_id: str,
    nickname: str,
    email: str,
    role: UserRole,
) -> str:
    return (
        f"[Layer {layer}] signup "
        f"login_id={login_id} nickname={nickname} email={email} role={role}"
    )


def format_preview_login(layer: int, *, login_id: str) -> str:
    return f"[Layer {layer}] login login_id={login_id}"


def format_preview_profile_request(layer: int, *, user_id: int) -> str:
    return f"[Layer {layer}] profile request user_id={user_id}"


def format_preview_profile_response(layer: int, *, user: dict[str, object]) -> str:
    return f"[Layer {layer}] profile response {user}"
