from fastapi import APIRouter, Depends

from core.security.dependencies import RoleChecker
from core.security.role import UserRole
from heyman.adapter.inbound.api.v1.discord_router import discord_router
from heyman.adapter.inbound.api.v1.email_router import email_router
from heyman.adapter.inbound.api.v1.judge_router import judge_router
from heyman.adapter.inbound.api.v1.juso_router import juso_router
from heyman.adapter.inbound.api.v1.receiver_router import receiver_router
from heyman.adapter.inbound.api.v1.telegram_router import telegram_router
from heyman.adapter.inbound.api.v1.watcher_router import watcher_router

# **하위 경로 전부 관리자 전용이다.** 연락처·받은편지함 조회, 전체 삭제, 외부 발송이
# 한 라우터에 있고, Next.js의 `requireAdmin`만으로는 `api.jsangho.cloud` 직통 요청을
# 막지 못한다. 경로마다 달지 않는 이유는 새 경로가 인증 없이 추가되지 않게 하려는 것이다.
#
# `/receiver/receive`·`/email/faker-report`의 원래 호출자는 n8n이었고 지금은 없다
# (2026-10-12에 내렸다). n8n을 되살리면 관리자 JWT를 들 수 없으므로 서버 간 인증을
# 따로 설계해야 한다 — 이 라우터에서 빼서 공개로 두면 안 된다.
_admin_only = RoleChecker(UserRole.ADMIN)

manager_router = APIRouter(
    prefix="/manager", tags=["manager"], dependencies=[Depends(_admin_only)]
)
manager_router.include_router(email_router)
manager_router.include_router(discord_router)
manager_router.include_router(juso_router)
manager_router.include_router(telegram_router)
manager_router.include_router(receiver_router)
manager_router.include_router(watcher_router)
manager_router.include_router(judge_router)

__all__ = ["manager_router"]
