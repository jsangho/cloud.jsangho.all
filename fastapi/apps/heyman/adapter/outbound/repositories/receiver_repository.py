from __future__ import annotations

import asyncio

from heyman.adapter.outbound.orm.receiver_orm import ReceiverOrm
from heyman.app.dtos.receiver_dto import ReceiverCommand, ReceiverItem
from heyman.app.ports.output.receiver_repository import ReceiverRepository
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from core.matrix.grid_oracle_database_manager import AsyncSessionLocal
from core.matrix.vault_keymaker_secret_manager import get_keymaker


class ReceiverPgRepository(ReceiverRepository):
    async def save(
        self, cmd: ReceiverCommand, spam_label: str, spam_confidence: float
    ) -> int:
        message_id = cmd.message_id or None

        if message_id is not None:
            async with AsyncSessionLocal() as session:
                existing_id = await session.scalar(
                    select(ReceiverOrm.id).where(ReceiverOrm.message_id == message_id)
                )
                if existing_id is not None:
                    return existing_id

        text = f"{cmd.subject} {cmd.body}".strip()
        embedding = await asyncio.to_thread(get_keymaker().embed_text, text)

        async with AsyncSessionLocal() as session:
            stmt = (
                pg_insert(ReceiverOrm)
                .values(
                    from_email=cmd.from_email,
                    from_name=cmd.from_name or None,
                    to_email=cmd.to_email or None,
                    subject=cmd.subject or None,
                    body=cmd.body or None,
                    message_id=message_id,
                    spam_label=spam_label,
                    spam_confidence=spam_confidence,
                    embedding=embedding,
                )
                .on_conflict_do_nothing(index_elements=["message_id"])
                .returning(ReceiverOrm.id)
            )
            inserted_id = await session.scalar(stmt)
            await session.commit()
            if inserted_id is not None:
                return inserted_id

            # 동시 요청으로 충돌한 경우 (Gmail Pub/Sub at-least-once 배달 대응)
            return await session.scalar(
                select(ReceiverOrm.id).where(ReceiverOrm.message_id == message_id)
            )

    async def list_all(self) -> list[ReceiverItem]:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(ReceiverOrm).order_by(ReceiverOrm.receiver_at.desc())
            )
            rows = result.scalars().all()
        return [
            ReceiverItem(
                id=r.id,
                from_email=r.from_email,
                from_name=r.from_name or "",
                to_email=r.to_email or "",
                subject=r.subject or "",
                body=r.body or "",
                message_id=r.message_id or "",
                receiver_at=r.receiver_at,
                is_read=r.is_read,
                spam_label=r.spam_label,
                spam_confidence=r.spam_confidence,
            )
            for r in rows
        ]

    async def mark_read(self, item_id: int) -> None:
        async with AsyncSessionLocal() as session:
            await session.execute(
                update(ReceiverOrm)
                .where(ReceiverOrm.id == item_id)
                .values(is_read=True)
            )
            await session.commit()
