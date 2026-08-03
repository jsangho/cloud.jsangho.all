"""모바일(Flutter) 인증 엔드포인트 — 하네스 §7 계약의 구현체.

필드 별칭은 기존 라우터 관례대로 camelCase다. Flutter 문서 §5와 글자 그대로
같아야 하므로, 한쪽을 고치면 반드시 다른 쪽도 고친다.
"""

from __future__ import annotations

from core.security.client_ip import client_ip
from core.security.dependencies import get_current_user
from core.security.token_verifier import TokenPayload
from pydantic import BaseModel, ConfigDict, Field

from auth.app.dtos.mobile_auth_dto import MobileDeviceDto
from auth.app.ports.input.mobile_auth_use_case import MobileAuthUseCase
from auth.app.ports.output.session_store import (
    MOBILE,
    SessionNotFoundError,
    SessionReuseDetectedError,
)
from auth.dependencies.auth_provider import get_mobile_auth_use_case
from fastapi import APIRouter, Depends, HTTPException, Request

mobile_auth_router = APIRouter(prefix="/mobile", tags=["auth-mobile"])

_INVALID_REFRESH = "리프레시 토큰이 유효하지 않습니다. 다시 로그인해 주세요."


class KakaoLoginRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    code: str = Field(..., min_length=1, description="카카오 인가 코드")
    redirect_uri: str = Field(..., alias="redirectUri", min_length=1)
    device_id: str = Field(..., alias="deviceId", min_length=1)
    device_name: str = Field(default="", alias="deviceName")
    os: str = Field(default="")
    app_version: str = Field(default="", alias="appVersion")


class MobileUserResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    user_id: int = Field(alias="userId")
    nickname: str
    # 카카오 이메일은 선택 동의 항목이라 null일 수 있다.
    email: str | None = None
    role: str


class LoginResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    token: str
    refresh_token: str = Field(alias="refreshToken")
    expires_in: int = Field(alias="expiresIn")
    user: MobileUserResponse


class RefreshRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    refresh_token: str = Field(..., alias="refreshToken", min_length=1)


class RefreshResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    token: str
    refresh_token: str = Field(alias="refreshToken")
    expires_in: int = Field(alias="expiresIn")


class DeviceSessionResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    jti: str
    device_id: str = Field(alias="deviceId")
    device_name: str = Field(alias="deviceName")
    os: str
    app_version: str = Field(alias="appVersion")
    issued_at: int = Field(alias="issuedAt")
    current: bool


class SessionListResponse(BaseModel):
    sessions: list[DeviceSessionResponse]


def _require_mobile(claims: TokenPayload) -> TokenPayload:
    """모바일 전용 엔드포인트를 웹 토큰으로 호출하지 못하게 막는다(D-3).

    `platform` 클레임이 없는 토큰은 이 기능 도입 이전에 발급된 것이므로 거부한다 —
    모바일 엔드포인트는 신규라 하위 호환을 지킬 대상이 없다.
    """
    if claims.platform != MOBILE:
        raise HTTPException(status_code=401, detail="모바일 세션이 아닙니다.")
    return claims


@mobile_auth_router.post(
    "/kakao", response_model=LoginResponse, response_model_by_alias=True
)
async def login_with_kakao(
    req: KakaoLoginRequest,
    request: Request,
    use_case: MobileAuthUseCase = Depends(get_mobile_auth_use_case),
):
    session = await use_case.login_with_kakao(
        code=req.code,
        redirect_uri=req.redirect_uri,
        device=MobileDeviceDto(
            device_id=req.device_id,
            device_name=req.device_name,
            os=req.os,
            app_version=req.app_version,
            ip=client_ip(request),
        ),
    )
    return LoginResponse(
        token=session.token,
        refresh_token=session.refresh_token,
        expires_in=session.expires_in,
        user=MobileUserResponse(
            user_id=session.user.user_id,
            nickname=session.user.nickname,
            email=session.user.email,
            role=session.user.role,
        ),
    )


@mobile_auth_router.post(
    "/refresh", response_model=RefreshResponse, response_model_by_alias=True
)
async def refresh(
    req: RefreshRequest,
    use_case: MobileAuthUseCase = Depends(get_mobile_auth_use_case),
):
    try:
        session = await use_case.refresh(refresh_token=req.refresh_token)
    except SessionReuseDetectedError as exc:
        # 이 시점에 모바일 세션은 전부 폐기됐다. 앱에는 재로그인만 안내한다.
        raise HTTPException(status_code=401, detail=_INVALID_REFRESH) from exc
    except (SessionNotFoundError, LookupError) as exc:
        raise HTTPException(status_code=401, detail=_INVALID_REFRESH) from exc

    return RefreshResponse(
        token=session.token,
        refresh_token=session.refresh_token,
        expires_in=session.expires_in,
    )


@mobile_auth_router.post("/logout")
async def logout(
    req: RefreshRequest,
    claims: TokenPayload = Depends(get_current_user),
    use_case: MobileAuthUseCase = Depends(get_mobile_auth_use_case),
):
    _require_mobile(claims)
    await use_case.logout(
        user_id=claims.sub,
        refresh_token=req.refresh_token,
        access_jti=claims.jti,
        access_exp=claims.exp,
    )
    return {"message": "로그아웃됐습니다."}


@mobile_auth_router.post("/logout-all")
async def logout_all(
    claims: TokenPayload = Depends(get_current_user),
    use_case: MobileAuthUseCase = Depends(get_mobile_auth_use_case),
):
    _require_mobile(claims)
    await use_case.logout_all(
        user_id=claims.sub, access_jti=claims.jti, access_exp=claims.exp
    )
    return {"message": "로그아웃됐습니다."}


@mobile_auth_router.get(
    "/sessions", response_model=SessionListResponse, response_model_by_alias=True
)
async def list_sessions(
    claims: TokenPayload = Depends(get_current_user),
    use_case: MobileAuthUseCase = Depends(get_mobile_auth_use_case),
):
    _require_mobile(claims)
    devices = await use_case.list_devices(
        user_id=claims.sub, current_device_id=claims.device_id or ""
    )
    return SessionListResponse(
        sessions=[
            DeviceSessionResponse(
                jti=d.jti,
                device_id=d.device_id,
                device_name=d.device_name,
                os=d.os,
                app_version=d.app_version,
                issued_at=d.issued_at,
                current=d.current,
            )
            for d in devices
        ]
    )
