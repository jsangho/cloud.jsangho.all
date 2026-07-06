from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from manager.app.dtos.judge_dto import JudgeQuery, JudgeResponse
from manager.app.ports.output.judge_repository import JudgeRepository


class JudgePgRepository(JudgeRepository):
    """Neon(Postgres) Judge 어댑터."""

    def __init__(self, session: AsyncSession | None = None) -> None:
        self._session = session

    async def introduce_myself(self, query: JudgeQuery) -> JudgeResponse:
        return JudgeResponse(
            id=query.id,
            name=query.name,
            description="Watson이 전달한 이벤트의 스팸 여부·처리 방침을 최종 판단하는 심사관입니다.",
        )
