from __future__ import annotations

from core.matrix.grid_oracle_database_manager import AsyncSessionLocal
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import HTTPException
from manager.adapter.outbound.orm.juso_orm import JusoContactOrm
from manager.app.dtos.juso_dto import ContactListItem, ContactRecordCommand
from manager.app.ports.output.juso_repository import JusoRepository

_BULK_CHUNK_SIZE = 300


def _optional_str(raw: str) -> str | None:
    value = (raw or "").strip()
    return value or None


def _contact_fields(cmd: ContactRecordCommand) -> dict[str, object]:
    return {
        "name": cmd.name.strip(),
        "given_name": _optional_str(cmd.given_name),
        "family_name": _optional_str(cmd.family_name),
        "nickname": _optional_str(cmd.nickname),
        "birthday": _optional_str(cmd.birthday),
        "gender": _optional_str(cmd.gender),
        "occupation": _optional_str(cmd.occupation),
        "notes": _optional_str(cmd.notes),
        "group_membership": _optional_str(cmd.group_membership),
        "email_1_value": _optional_str(cmd.email_1_value),
        "email_2_value": _optional_str(cmd.email_2_value),
        "phone_1_value": _optional_str(cmd.phone_1_value),
        "phone_2_value": _optional_str(cmd.phone_2_value),
        "address_1_formatted": _optional_str(cmd.address_1_formatted),
        "address_1_street": _optional_str(cmd.address_1_street),
        "address_1_city": _optional_str(cmd.address_1_city),
        "address_1_region": _optional_str(cmd.address_1_region),
        "address_1_postal_code": _optional_str(cmd.address_1_postal_code),
        "address_1_country": _optional_str(cmd.address_1_country),
        "org_name": _optional_str(cmd.org_name),
        "org_title": _optional_str(cmd.org_title),
        "org_department": _optional_str(cmd.org_department),
        "website_1_value": _optional_str(cmd.website_1_value),
    }


class JusoPgRepository(JusoRepository):
    """pgvector(Docker Postgres) 연락처 업로드 어댑터."""

    def __init__(self, session: AsyncSession | None = None) -> None:
        self._session = session

    async def upload_contacts(self, commands: list[ContactRecordCommand]) -> int:
        if AsyncSessionLocal is None:
            raise HTTPException(
                status_code=503,
                detail="DATABASE_URL이 .env 등에 설정되지 않았습니다.",
            )

        if self._session is None:
            async with AsyncSessionLocal() as session:
                count = await self._save_contacts(session, commands)
                await session.commit()
        else:
            count = await self._save_contacts(self._session, commands)
            await self._session.commit()

        return count

    async def _save_contacts(
        self,
        session: AsyncSession,
        commands: list[ContactRecordCommand],
    ) -> int:
        rows = [_contact_fields(cmd) for cmd in commands if cmd.name.strip()]
        if not rows:
            return 0

        # 같은 배치 내 email_1_value 중복 시 PostgreSQL CardinalityViolation 방지
        # email이 없는 행은 중복 허용, email이 있는 행은 마지막 값으로 deduplicate
        seen_emails: set[str] = set()
        deduped: list[dict] = []
        for row in reversed(rows):
            email = row.get("email_1_value")
            if email:
                if email in seen_emails:
                    continue
                seen_emails.add(email)
            deduped.append(row)
        rows = list(reversed(deduped))

        for chunk_start in range(0, len(rows), _BULK_CHUNK_SIZE):
            chunk = rows[chunk_start : chunk_start + _BULK_CHUNK_SIZE]
            stmt = pg_insert(JusoContactOrm).values(chunk)
            await session.execute(
                stmt.on_conflict_do_update(
                    index_elements=[JusoContactOrm.email_1_value],
                    set_={
                        "name": stmt.excluded.name,
                        "given_name": stmt.excluded.given_name,
                        "family_name": stmt.excluded.family_name,
                        "nickname": stmt.excluded.nickname,
                        "birthday": stmt.excluded.birthday,
                        "gender": stmt.excluded.gender,
                        "occupation": stmt.excluded.occupation,
                        "notes": stmt.excluded.notes,
                        "group_membership": stmt.excluded.group_membership,
                        "email_2_value": stmt.excluded.email_2_value,
                        "phone_1_value": stmt.excluded.phone_1_value,
                        "phone_2_value": stmt.excluded.phone_2_value,
                        "address_1_formatted": stmt.excluded.address_1_formatted,
                        "address_1_street": stmt.excluded.address_1_street,
                        "address_1_city": stmt.excluded.address_1_city,
                        "address_1_region": stmt.excluded.address_1_region,
                        "address_1_postal_code": stmt.excluded.address_1_postal_code,
                        "address_1_country": stmt.excluded.address_1_country,
                        "org_name": stmt.excluded.org_name,
                        "org_title": stmt.excluded.org_title,
                        "org_department": stmt.excluded.org_department,
                        "website_1_value": stmt.excluded.website_1_value,
                    },
                )
            )

        return len(rows)

    async def delete_all_contacts(self) -> int:
        if AsyncSessionLocal is None:
            return 0
        async with AsyncSessionLocal() as session:
            result = await session.execute(delete(JusoContactOrm))
            await session.commit()
        return result.rowcount

    async def list_contacts(self) -> list[ContactListItem]:
        if AsyncSessionLocal is None:
            return []
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(JusoContactOrm).order_by(JusoContactOrm.id)
            )
            rows = result.scalars().all()
        return [
            ContactListItem(
                id=row.id,
                name=row.name or "",
                email=row.email_1_value or "",
                phone=row.phone_1_value or "",
                org_name=row.org_name or "",
            )
            for row in rows
        ]
