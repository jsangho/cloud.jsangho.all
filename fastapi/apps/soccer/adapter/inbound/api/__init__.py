from fastapi import APIRouter
from soccer.adapter.inbound.api.v1.soccer_chat_router import soccer_chat_router

soccer_router = APIRouter(tags=["soccer"])
soccer_router.include_router(soccer_chat_router)

__all__ = ["soccer_router"]
