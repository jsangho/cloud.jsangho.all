from fastapi import APIRouter, Depends
from heyman.adapter.inbound.api.schemas.judge_schema import JudgeMyselfSchema
from heyman.app.dtos.judge_dto import JudgeQuery, JudgeResponse
from heyman.app.ports.input.judge_use_case import JudgeUseCase
from heyman.dependencies.judge_provider import get_judge_use_case

judge_router = APIRouter(prefix="/judge", tags=["judge"])


@judge_router.get("/myself")
async def introduce_myself(
    use_case: JudgeUseCase = Depends(get_judge_use_case),
) -> JudgeResponse:
    schema = JudgeMyselfSchema()
    query = JudgeQuery(id=schema.id, name=schema.name)
    return await use_case.introduce_myself(query)
