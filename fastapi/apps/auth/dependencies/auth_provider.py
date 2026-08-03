from __future__ import annotations

from core.matrix.grid_oracle_database_manager import get_db
from sqlalchemy.ext.asyncio import AsyncSession

from auth.adapter.outbound.google_oauth_client import GoogleOAuthClient
from auth.adapter.outbound.kakao_mobile_oauth_client import KakaoMobileOAuthClient
from auth.adapter.outbound.kakao_oauth_client import KakaoOAuthClient
from auth.adapter.outbound.naver_oauth_client import NaverOAuthClient
from auth.adapter.outbound.pg.user_pg_repository import UserPgRepository
from auth.adapter.outbound.redis.kakao_token_redis_vault import KakaoTokenRedisVault
from auth.adapter.outbound.redis.oauth_state_redis_store import OAuthStateRedisStore
from auth.adapter.outbound.redis.refresh_token_repository import (
    RefreshTokenRepository,
)
from auth.adapter.outbound.redis.session_redis_store import SessionRedisStore
from auth.app.ports.input.login_use_case import LoginUseCase
from auth.app.ports.input.mobile_auth_use_case import MobileAuthUseCase
from auth.app.ports.input.oauth_login_use_case import OAuthLoginUseCase
from auth.app.ports.input.profile_use_case import ProfileUseCase
from auth.app.ports.input.signup_use_case import SignupUseCase
from auth.app.use_cases.login_interactor import LoginInteractor
from auth.app.use_cases.mobile_auth_interactor import MobileAuthInteractor
from auth.app.use_cases.oauth_login_interactor import OAuthLoginInteractor
from auth.app.use_cases.profile_interactor import ProfileInteractor
from auth.app.use_cases.signup_interactor import SignupInteractor
from fastapi import Depends


def get_login_use_case(db: AsyncSession = Depends(get_db)) -> LoginUseCase:
    return LoginInteractor(UserPgRepository(db))


def get_signup_use_case(db: AsyncSession = Depends(get_db)) -> SignupUseCase:
    return SignupInteractor(UserPgRepository(db))


def get_profile_use_case(db: AsyncSession = Depends(get_db)) -> ProfileUseCase:
    return ProfileInteractor(UserPgRepository(db))


def get_google_login_use_case(db: AsyncSession = Depends(get_db)) -> OAuthLoginUseCase:
    return OAuthLoginInteractor(
        provider="google",
        identity_provider=GoogleOAuthClient(),
        repository=UserPgRepository(db),
        state_store=OAuthStateRedisStore(),
    )


def get_kakao_login_use_case(db: AsyncSession = Depends(get_db)) -> OAuthLoginUseCase:
    return OAuthLoginInteractor(
        provider="kakao",
        identity_provider=KakaoOAuthClient(),
        repository=UserPgRepository(db),
        state_store=OAuthStateRedisStore(),
    )


def get_naver_login_use_case(db: AsyncSession = Depends(get_db)) -> OAuthLoginUseCase:
    return OAuthLoginInteractor(
        provider="naver",
        identity_provider=NaverOAuthClient(),
        repository=UserPgRepository(db),
        state_store=OAuthStateRedisStore(),
    )


def get_refresh_token_repository() -> RefreshTokenRepository:
    return RefreshTokenRepository()


def get_mobile_auth_use_case(db: AsyncSession = Depends(get_db)) -> MobileAuthUseCase:
    """모바일 인증 배선.

    `KakaoTokenRedisVault` 생성 시 `KAKAO_RT_ENCRYPTION_KEY`가 없으면 여기서 즉시
    RuntimeError가 난다 — 카카오 토큰을 평문으로 저장하는 경로를 만들지 않기 위해서다.
    웹 로그인은 이 팩토리를 거치지 않으므로 영향을 받지 않는다.
    """
    return MobileAuthInteractor(
        kakao=KakaoMobileOAuthClient(),
        users=UserPgRepository(db),
        sessions=SessionRedisStore(),
        kakao_vault=KakaoTokenRedisVault(),
    )
