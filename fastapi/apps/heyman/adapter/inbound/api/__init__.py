from fastapi import APIRouter
from heyman.adapter.inbound.api.v1.discord_router import discord_router
from heyman.adapter.inbound.api.v1.email_router import email_router
from heyman.adapter.inbound.api.v1.judge_router import judge_router
from heyman.adapter.inbound.api.v1.juso_router import juso_router
from heyman.adapter.inbound.api.v1.receiver_router import receiver_router
from heyman.adapter.inbound.api.v1.telegram_router import telegram_router
from heyman.adapter.inbound.api.v1.watcher_router import watcher_router

manager_router = APIRouter(prefix="/manager", tags=["manager"])
manager_router.include_router(email_router)
manager_router.include_router(discord_router)
manager_router.include_router(juso_router)
manager_router.include_router(telegram_router)
manager_router.include_router(receiver_router)
manager_router.include_router(watcher_router)
manager_router.include_router(judge_router)

__all__ = ["manager_router"]
