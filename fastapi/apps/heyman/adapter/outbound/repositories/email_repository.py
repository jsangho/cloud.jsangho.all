from __future__ import annotations

from fastapi import HTTPException
from heyman.adapter.outbound.orm.email_orm import EmailOrm
from heyman.app.dtos.email_dto import EmailDto
from heyman.app.ports.output.email_repository import EmailRepository
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.matrix.grid_oracle_database_manager import AsyncSessionLocal, Base, engine


async def _ensure_email_table() -> None:
    if engine is None:
        raise HTTPException(
            status_code=503,
            detail="DATABASE_URL이 .env 등에 설정되지 않았습니다.",
        )
    import manager.adapter.outbound.orm.email_orm  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_notifications_to_email "
                "ON notifications (to_email)"
            )
        )


class EmailPgRepository(EmailRepository):
    def __init__(self, session: AsyncSession | None = None) -> None:
        self._session = session

    async def save(self, dto: EmailDto, status: str) -> int:
        if AsyncSessionLocal is None:
            raise HTTPException(
                status_code=503,
                detail="DATABASE_URL이 .env 등에 설정되지 않았습니다.",
            )

        await _ensure_email_table()

        row = EmailOrm(
            to_email=dto.to,
            subject=dto.subject,
            body=dto.body,
            status=status,
        )

        if self._session is None:
            async with AsyncSessionLocal() as session:
                session.add(row)
                await session.commit()
                await session.refresh(row)
        else:
            self._session.add(row)
            await self._session.commit()
            await self._session.refresh(row)

        return row.id
