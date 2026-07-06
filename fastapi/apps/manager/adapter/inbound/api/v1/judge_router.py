from fastapi import APIRouter, Depends
from manager.adapter.inbound.api.schemas.judge_schema import JudgeMyselfSchema
from manager.app.dtos.judge_dto import JudgeQuery, JudgeResponse
from manager.app.ports.input.judge_use_case import JudgeUseCase
from manager.dependencies.judge_provider import get_judge_use_case

judge_router = APIRouter(prefix="/judge", tags=["judge"])


@judge_router.get("/myself")
async def introduce_myself(
    use_case: JudgeUseCase = Depends(get_judge_use_case),
) -> JudgeResponse:
    schema = JudgeMyselfSchema()
    query = JudgeQuery(id=schema.id, name=schema.name)
    return await use_case.introduce_myself(query)
