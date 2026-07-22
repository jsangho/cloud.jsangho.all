from __future__ import annotations

from enum import StrEnum


class UserRole(StrEnum):
    USER = "user"
    ADMIN = "admin"


class Permission(StrEnum):
    READ_OWN_PROFILE = "read_own_profile"
    READ_ANY_PROFILE = "read_any_profile"
    VIEW_ADMIN_DOCS = "view_admin_docs"


ROLE_PERMISSIONS: dict[UserRole, frozenset[Permission]] = {
    UserRole.USER: frozenset({Permission.READ_OWN_PROFILE}),
    UserRole.ADMIN: frozenset(
        {
            Permission.READ_OWN_PROFILE,
            Permission.READ_ANY_PROFILE,
            Permission.VIEW_ADMIN_DOCS,
        }
    ),
}


def permissions_for(role: UserRole) -> frozenset[Permission]:
    return ROLE_PERMISSIONS.get(role, frozenset())
