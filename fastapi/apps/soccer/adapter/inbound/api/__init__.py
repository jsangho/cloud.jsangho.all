from soccer.adapter.inbound.api.v1.soccer_chat_router import soccer_chat_router

from fastapi import APIRouter

soccer_router = APIRouter(tags=["soccer"])
soccer_router.include_router(soccer_chat_router)

__all__ = ["soccer_router"]
