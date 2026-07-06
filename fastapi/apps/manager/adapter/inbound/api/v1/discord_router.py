from fastapi import APIRouter, Depends
from manager.adapter.inbound.api.schemas.discord_schema import DiscordMyselfSchema
from manager.app.dtos.discord_dto import DiscordQuery, DiscordResponse
from manager.app.ports.input.discord_use_case import DiscordUseCase
from manager.dependencies.discord_provider import get_discord_use_case

discord_router = APIRouter(prefix="/discord", tags=["discord"])


@discord_router.get("/myself")
async def introduce_myself(
    use_case: DiscordUseCase = Depends(get_discord_use_case),
) -> DiscordResponse:
    schema = DiscordMyselfSchema()
    query = DiscordQuery(id=schema.id, name=schema.name)
    return await use_case.introduce_myself(query)
