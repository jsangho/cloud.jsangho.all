from fastapi import APIRouter
from human_resource.adapter.inbound.api.v1.piper_bighetti_hr_router import (
    bighetti_hr_router,
)
from human_resource.adapter.inbound.api.v1.piper_dinesh_dash_router import (
    dinesh_dash_router,
)
from human_resource.adapter.inbound.api.v1.piper_dunn_coo_router import dunn_coo_router
from human_resource.adapter.inbound.api.v1.piper_gilfoyle_sys_router import (
    gilfoyle_sys_router,
)
from human_resource.adapter.inbound.api.v1.piper_hendricks_ceo_router import (
    hendricks_ceo_router,
)

human_resource_router = APIRouter(prefix="/human_resource", tags=["human_resource"])
human_resource_router.include_router(hendricks_ceo_router)
human_resource_router.include_router(bighetti_hr_router)
human_resource_router.include_router(dinesh_dash_router)
human_resource_router.include_router(dunn_coo_router)
human_resource_router.include_router(gilfoyle_sys_router)

__all__ = ["human_resource_router"]
