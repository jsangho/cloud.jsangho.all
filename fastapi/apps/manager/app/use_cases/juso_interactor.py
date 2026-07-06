from __future__ import annotations

from manager.app.dtos.juso_dto import (
    ContactListItem,
    ContactRecordCommand,
    JusoQuery,
    JusoResponse,
)
from manager.app.ports.input.juso_use_case import JusoUseCase
from manager.app.ports.output.juso_repository import JusoRepository


class JusoInteractor(JusoUseCase):
    def __init__(self, repository: JusoRepository) -> None:
        self._repository = repository

    async def introduce_myself(self, query: JusoQuery) -> JusoResponse:
        return JusoResponse(
            id=query.id,
            name=query.name,
            description="행정안전부 도로명 주소 API로 주소를 검색하는 서비스입니다.",
        )

    async def upload_contacts(
        self, commands: list[ContactRecordCommand]
    ) -> dict[str, int]:
        count = await self._repository.upload_contacts(commands)
        return {"count": count}

    async def list_contacts(self) -> list[ContactListItem]:
        return await self._repository.list_contacts()

    async def delete_all_contacts(self) -> dict[str, int]:
        count = await self._repository.delete_all_contacts()
        return {"deleted": count}
