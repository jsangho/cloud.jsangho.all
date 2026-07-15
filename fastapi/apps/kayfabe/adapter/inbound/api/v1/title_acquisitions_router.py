from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from kayfabe.adapter.inbound.api.schemas.ple_events_schema import MyselfSchema
from kayfabe.adapter.inbound.api.schemas.title_acquisitions_schema import (
    ChampionshipBoardResponseSchema,
    CompetitorTitleHistoryResponseSchema,
)
from kayfabe.app.dtos.ple_events_dto import MyselfQuery, MyselfResponse, MyselfUseCase
from kayfabe.app.ports.input.title_acquisitions_use_case import TitleAcquisitionsUseCase
from kayfabe.dependencies.title_acquisitions_provider import get_title_acquisitions

logger = logging.getLogger("uvicorn.error")

title_acquisitions_router = APIRouter(
    prefix="/title-acquisitions", tags=["title-acquisitions"]
)


@title_acquisitions_router.get("/myself", response_model=None)
async def introduce_title_myself(
    use_case: MyselfUseCase = Depends(get_title_acquisitions),
) -> MyselfResponse:
    schema = MyselfSchema(id=6, name="title_acquisitions_router")
    query = MyselfQuery(id=schema.id, name=schema.name)
    return await use_case.introduce_myself(query)


@title_acquisitions_router.get(
    "/competitors/{name}",
    response_model=CompetitorTitleHistoryResponseSchema,
    response_model_by_alias=True,
)
async def get_competitor_title_history(
    name: str,
    use_case: TitleAcquisitionsUseCase = Depends(get_title_acquisitions),
):
    """선수/팀의 실제 WWE 챔피언십 벨트 획득 이력 (NeonDB)."""
    return (await use_case.get_competitor_title_history(name)).to_schema()


@title_acquisitions_router.post("/sync")
async def sync_title_history_from_catalog(
    use_case: TitleAcquisitionsUseCase = Depends(get_title_acquisitions),
):
    """실제 WWE 타이틀 획득 카탈로그로 NeonDB를 재생성."""
    count = await use_case.sync_from_real_catalog()
    return {"synced": count}


@title_acquisitions_router.get(
    "/",
    response_model=ChampionshipBoardResponseSchema,
    response_model_by_alias=True,
)
async def get_championship_board(
    use_case: TitleAcquisitionsUseCase = Depends(get_title_acquisitions),
):
    """브랜드별 현역 WWE 챔피언 (메인·2선·태그·기타)."""
    logger.info("[TitleAcquisitionsRouter] get_championship_board")
    return (await use_case.get_board()).to_schema()
