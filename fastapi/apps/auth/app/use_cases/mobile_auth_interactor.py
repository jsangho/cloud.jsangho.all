from __future__ import annotations

import re
import secrets
import time

from core.entities.user_model import UserModel
from core.security.role import UserRole

from auth.app.dtos.mobile_auth_dto import (
    MobileDeviceDto,
    MobileDeviceSessionDto,
    MobileLoginDto,
    MobileSessionDto,
    MobileUserDto,
)
from auth.app.ports.input.mobile_auth_use_case import MobileAuthUseCase
from auth.app.ports.output.kakao_mobile_identity_provider import (
    KakaoMobileIdentityProvider,
)
from auth.app.ports.output.kakao_token_vault import KakaoTokenVault
from auth.app.ports.output.session_store import (
    MOBILE,
    SessionMeta,
    SessionStore,
)
from auth.app.ports.output.user_repository import UserRepository
from auth.domain.services.token_issuer import (
    ACCESS_TOKEN_EXPIRES_SECONDS,
    create_access_token,
)
from auth.domain.value_objects.kakao_identity import KakaoProfile

_LOGIN_ID_SAFE_CHARS = re.compile(r"[^a-zA-Z0-9_]+")
_PROVIDER = "kakao"


class MobileAuthInteractor(MobileAuthUseCase):
    def __init__(
        self,
        *,
        kakao: KakaoMobileIdentityProvider,
        users: UserRepository,
        sessions: SessionStore,
        kakao_vault: KakaoTokenVault,
    ) -> None:
        self._kakao = kakao
        self._users = users
        self._sessions = sessions
        self._kakao_vault = kakao_vault

    async def login_with_kakao(
        self, *, code: str, redirect_uri: str, device: MobileDeviceDto
    ) -> MobileLoginDto:
        token_set = await self._kakao.exchange_code(
            code=code, redirect_uri=redirect_uri
        )
        profile = await self._kakao.fetch_profile(access_token=token_set.access_token)

        user = await self._upsert(profile)
        user_id = str(user.id)

        # 카카오 refresh token은 서버에만 남는다 — 앱으로 내려보내지 않는다(D-1).
        await self._kakao_vault.store(
            user_id=user_id, refresh_token=token_set.refresh_token
        )

        refresh_token, _ = await self._sessions.create_session(
            platform=MOBILE,
            user_id=user_id,
            meta=SessionMeta(
                device_id=device.device_id,
                device_name=device.device_name,
                app_version=device.app_version,
                os=device.os,
                ip=device.ip,
            ),
        )
        role = UserRole(user.role)
        return MobileLoginDto(
            token=create_access_token(
                sub=user_id,
                roles=[role.value],
                platform=MOBILE,
                device_id=device.device_id,
            ),
            refresh_token=refresh_token,
            expires_in=ACCESS_TOKEN_EXPIRES_SECONDS,
            user=MobileUserDto(
                user_id=user.id,
                nickname=user.nickname,
                email=user.email,
                role=role.value,
            ),
        )

    async def refresh(self, *, refresh_token: str) -> MobileSessionDto:
        new_token, _, user_id = await self._sessions.rotate_session(
            platform=MOBILE, refresh_token=refresh_token
        )

        user = await self._users.find_by_id(user_id=int(user_id))
        if user is None:
            # 세션은 살아 있는데 유저가 사라졌다 — 세션도 함께 정리한다.
            await self._sessions.revoke_all(platform=MOBILE, user_id=user_id)
            raise LookupError(f"user {user_id} not found")

        role = UserRole(user.role)
        return MobileSessionDto(
            token=create_access_token(sub=user_id, roles=[role.value], platform=MOBILE),
            refresh_token=new_token,
            expires_in=ACCESS_TOKEN_EXPIRES_SECONDS,
        )

    async def logout(
        self, *, user_id: str, refresh_token: str, access_jti: str, access_exp: int
    ) -> None:
        jti = refresh_token.split(".", 1)[0]
        await self._sessions.revoke_session(platform=MOBILE, user_id=user_id, jti=jti)
        await self._blacklist(access_jti, access_exp)

    async def logout_all(
        self, *, user_id: str, access_jti: str, access_exp: int
    ) -> None:
        await self._sessions.revoke_all(platform=MOBILE, user_id=user_id)
        await self._blacklist(access_jti, access_exp)

    async def list_devices(
        self, *, user_id: str, current_device_id: str
    ) -> list[MobileDeviceSessionDto]:
        sessions = await self._sessions.list_sessions(platform=MOBILE, user_id=user_id)
        return [
            MobileDeviceSessionDto(
                jti=s.jti,
                device_id=s.device_id,
                device_name=s.device_name,
                os=s.os,
                app_version=s.app_version,
                issued_at=s.issued_at,
                current=bool(current_device_id) and s.device_id == current_device_id,
            )
            for s in sessions
        ]

    async def _blacklist(self, jti: str, exp: int) -> None:
        await self._sessions.blacklist_access_token(
            jti=jti, ttl_seconds=max(exp - int(time.time()), 0)
        )

    async def _upsert(self, profile: KakaoProfile) -> UserModel:
        """카카오 회원번호로만 계정을 찾는다.

        웹 경로에 있는 `find_by_email` 폴백을 여기서는 쓰지 않는다 — 미검증 이메일로
        기존 계정에 올라타면 계정 탈취가 된다(T3).
        """
        user = await self._users.find_by_oauth(
            provider=_PROVIDER, oauth_id=profile.kakao_id
        )
        if user is not None:
            return user

        login_id = await self._unique_login_id(profile)
        return await self._users.create_oauth_user(
            login_id=login_id,
            nickname=profile.nickname or login_id,
            email=profile.email,
            provider=_PROVIDER,
            oauth_id=profile.kakao_id,
        )

    async def _unique_login_id(self, profile: KakaoProfile) -> str:
        if profile.email:
            base = _LOGIN_ID_SAFE_CHARS.sub("_", profile.email.split("@", 1)[0])
        else:
            # 이메일이 없으면 회원번호로 만든다. 카카오 회원번호는 앱 단위로 고유하다.
            base = f"kakao_{profile.kakao_id}"
        base = base.strip("_") or "user"

        candidate = base
        while await self._users.find_by_login_id(login_id=candidate) is not None:
            candidate = f"{base}_{secrets.token_hex(3)}"
        return candidate
