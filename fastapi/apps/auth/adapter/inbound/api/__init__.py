from auth.adapter.inbound.api.login_router import login_router
from auth.adapter.inbound.api.logout_router import logout_router
from auth.adapter.inbound.api.oauth_callback_router import oauth_callback_router
from auth.adapter.inbound.api.refresh_router import refresh_router
from fastapi import APIRouter

auth_router = APIRouter(tags=["auth"])
auth_router.include_router(login_router)
auth_router.include_router(logout_router)
auth_router.include_router(refresh_router)
auth_router.include_router(oauth_callback_router)

__all__ = ["auth_router"]
