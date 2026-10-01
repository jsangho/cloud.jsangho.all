from __future__ import annotations

import logging

import fastapi
from fastapi import APIRouter, Depends

from core.security.dependencies import RoleChecker
from core.security.role import UserRole
from core.security.token_verifier import TokenPayload
from kayfabe.adapter.inbound.api.schemas.ple_events_schema import MyselfSchema
from kayfabe.adapter.inbound.api.schemas.ple_matches_schema import (
    BatchResultsRequestSchema,
    CompetitorListResponseSchema,
    CompetitorProfileResponseSchema,
    MatchResultUpdateSchema,
    PleBoardSchema,
)
from kayfabe.adapter.outbound.mappers.ple_schema_mapper import (
    batch_results_from_schema,
    board_to_schema,
    match_result_update_from_schema,
)
from kayfabe.app.dtos.ple_events_dto import MyselfQuery, MyselfResponse, MyselfUseCase
from kayfabe.app.ports.input.ple_events_use_case import PleEventsUseCase
from kayfabe.app.ports.input.ple_matches_use_case import PleMatchesUseCase
from kayfabe.dependencies.ple_events_provider import get_ple_events
from kayfabe.dependencies.ple_matches_provider import get_ple_matches

logger = logging.getLogger("uvicorn.error")

ple_matches_router = APIRouter(prefix="/ple-matches", tags=["ple-matches"])

# 경기 결과를 쓰는 두 엔드포인트는 **관리자만** 부른다.
#
# 이 문을 잠그기 전까지 승자 입력은 프론트의 `lib/ple-results-admin.ts`에 박힌
# 비밀번호 하나로만 가려져 있었다. 그건 브라우저 코드라 누구나 읽을 수 있고, 서버는
# 토큰을 아예 보지 않았으므로 **아무나 운영 대회의 승자를 바꿀 수 있었다** — 결과는
# 사용자 픽 채점과 랭킹의 입력이라, 한 번 뒤집히면 그 뒤 숫자가 전부 따라 틀린다.
#
# 조회(`/{slug}` 보드)는 그대로 공개다. 잠그는 것은 쓰기뿐이다.
_admin_only = RoleChecker(UserRole.ADMIN)


def _ple_http_error(exc: Exception) -> fastapi.HTTPException:
    if isinstance(exc, LookupError):
        return fastapi.HTTPException(status_code=404, detail=str(exc) or "Not found")
    if isinstance(exc, ValueError):
        return fastapi.HTTPException(
            status_code=400, detail=str(exc) or "잘못된 요청입니다."
        )
    raise exc


@ple_matches_router.get("/myself", response_model=None)
async def introduce_records_myself(
    use_case: MyselfUseCase = Depends(get_ple_matches),
) -> MyselfResponse:
    schema = MyselfSchema(id=5, name="ple_matches_router")
    query = MyselfQuery(id=schema.id, name=schema.name)
    return await use_case.introduce_myself(query)


@ple_matches_router.get(
    "/competitors",
    response_model=CompetitorListResponseSchema,
    response_model_by_alias=True,
)
async def list_competitors(
    q: str | None = None,
    use_case: PleMatchesUseCase = fastapi.Depends(get_ple_matches),
):
    logger.info("[PleMatchesRouter] list_competitors | q=%s", q or "-")
    return (await use_case.list_competitors(q=q)).to_schema()


@ple_matches_router.get(
    "/competitors/{name}",
    response_model=CompetitorProfileResponseSchema,
    response_model_by_alias=True,
)
async def get_competitor_profile(
    name: str,
    use_case: PleMatchesUseCase = fastapi.Depends(get_ple_matches),
):
    logger.info("[PleMatchesRouter] get_competitor_profile | name=%s", name)
    profile = await use_case.get_competitor_profile(name)
    if not profile.matches and not await _competitor_exists(use_case, name):
        raise fastapi.HTTPException(status_code=404, detail="선수를 찾을 수 없습니다.")
    return profile.to_schema()


async def _competitor_exists(use_case: PleMatchesUseCase, name: str) -> bool:
    listed = await use_case.list_competitors()
    target = name.strip().lower()
    return any(n.lower() == target for n in listed.names)


@ple_matches_router.post(
    "/{slug}/results/batch",
    response_model=PleBoardSchema,
    response_model_by_alias=True,
)
async def set_ple_results_batch(
    slug: str,
    body: BatchResultsRequestSchema,
    _: TokenPayload = Depends(_admin_only),
    use_case: PleEventsUseCase = fastapi.Depends(get_ple_events),
):
    logger.info(
        "[PleMatchesRouter] set_ple_results_batch | slug=%s count=%d",
        slug,
        len(body.results),
    )
    try:
        board = await use_case.set_match_results_batch(
            slug=slug,
            body=batch_results_from_schema(body),
        )
        return board_to_schema(board)
    except (LookupError, ValueError) as e:
        raise _ple_http_error(e) from e


@ple_matches_router.post(
    "/{slug}/matches/{match_key}/result",
    response_model=PleBoardSchema,
    response_model_by_alias=True,
)
async def set_ple_match_result(
    slug: str,
    match_key: str,
    body: MatchResultUpdateSchema,
    _: TokenPayload = Depends(_admin_only),
    use_case: PleEventsUseCase = fastapi.Depends(get_ple_events),
):
    logger.info(
        "[PleMatchesRouter] set_ple_match_result | slug=%s match=%s", slug, match_key
    )
    try:
        board = await use_case.set_match_result(
            slug=slug,
            match_key=match_key,
            body=match_result_update_from_schema(body),
        )
        return board_to_schema(board)
    except (LookupError, ValueError) as e:
        raise _ple_http_error(e) from e
