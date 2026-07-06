from fastapi import APIRouter
from superstar.adapter.inbound.api.v1.jason_mask_router import jason_mask_router
from superstar.adapter.inbound.api.v1.murder_list_router import murder_list_router
from superstar.adapter.inbound.api.v1.pamela_cook_router import pamela_cook_router

user_router = APIRouter(tags=["user"])
user_router.include_router(jason_mask_router)
user_router.include_router(pamela_cook_router)
user_router.include_router(murder_list_router)

__all__ = ["user_router"]
