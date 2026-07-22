from __future__ import annotations

from core.matrix.grid_oracle_database_manager import get_db
from sqlalchemy.ext.asyncio import AsyncSession

from auth.adapter.outbound.google_oauth_client import GoogleOAuthClient
from auth.adapter.outbound.kakao_oauth_client import KakaoOAuthClient
from auth.adapter.outbound.naver_oauth_client import NaverOAuthClient
from auth.adapter.outbound.pg.user_pg_repository import UserPgRepository
from auth.adapter.outbound.redis.refresh_token_repository import (
    RefreshTokenRepository,
)
from auth.app.ports.input.login_use_case import LoginUseCase
from auth.app.ports.input.oauth_login_use_case import OAuthLoginUseCase
from auth.app.ports.input.profile_use_case import ProfileUseCase
from auth.app.ports.input.signup_use_case import SignupUseCase
from auth.app.use_cases.login_interactor import LoginInteractor
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
    )


def get_kakao_login_use_case(db: AsyncSession = Depends(get_db)) -> OAuthLoginUseCase:
    return OAuthLoginInteractor(
        provider="kakao",
        identity_provider=KakaoOAuthClient(),
        repository=UserPgRepository(db),
    )


def get_naver_login_use_case(db: AsyncSession = Depends(get_db)) -> OAuthLoginUseCase:
    return OAuthLoginInteractor(
        provider="naver",
        identity_provider=NaverOAuthClient(),
        repository=UserPgRepository(db),
    )


def get_refresh_token_repository() -> RefreshTokenRepository:
    return RefreshTokenRepository()
