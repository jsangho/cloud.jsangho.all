from __future__ import annotations

from core.matrix.grid_oracle_database_manager import AsyncSessionLocal, Base, engine
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import HTTPException
from titanic.adapter.outbound.orm.passenger_jack_trainer_orm import JackTrainerOrm
from titanic.adapter.outbound.orm.passenger_rose_model_strategies import RoseModelOrm
from titanic.app.dtos.crew_james_director_dto import (
    BookingCommand,
    JamesDirectorQuery,
    JamesDirectorResponse,
    PersonCommand,
)
from titanic.app.ports.output.crew_james_director_port import JamesDirectorPort

_BULK_CHUNK_SIZE = 300


def _optional_str(raw: str) -> str | None:
    value = (raw or "").strip()
    return value or None


def _person_fields(cmd: PersonCommand, passenger_id: str) -> dict[str, object]:
    return {
        "passenger_id": passenger_id,
        "name": _optional_str(cmd.name),
        "gender": _optional_str(cmd.gender),
        "age": _optional_str(cmd.age),
        "sib_sp": _optional_str(cmd.sib_sp),
        "parch": _optional_str(cmd.parch),
        "survived": _optional_str(cmd.survived),
    }


def _booking_fields(cmd: BookingCommand) -> dict[str, object]:
    cabin = _optional_str(cmd.cabin)
    embarked = _optional_str(cmd.embarked)
    ticket = _optional_str(cmd.ticket)
    return {
        "pclass": _optional_str(cmd.pclass),
        "ticket": ticket[:64] if ticket else None,
        "fare": _optional_str(cmd.fare),
        "cabin": cabin[:32] if cabin else None,
        "embarked": embarked[:1] if embarked else None,
    }


async def _ensure_james_director_tables() -> None:
    """Neon에 persons / bookings 테이블이 없으면 생성."""
    if engine is None:
        raise HTTPException(
            status_code=503,
            detail="DATABASE_URL이 .env 등에 설정되지 않았습니다.",
        )
    import titanic.adapter.outbound.orm.passenger_jack_trainer_orm  # noqa: F401
    import titanic.adapter.outbound.orm.passenger_rose_model_strategies  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_passengers_passenger_id "
                "ON passengers (passenger_id)"
            )
        )
        await conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_bookings_passenger_id "
                "ON bookings (passenger_id)"
            )
        )


class JamesDirectorRepository(JamesDirectorPort):
    """Neon(Postgres) James Director 업로드 어댑터."""

    def __init__(self, session: AsyncSession | None) -> None:
        self._session = session

    async def introduce_myself(
        self, query: JamesDirectorQuery
    ) -> JamesDirectorResponse:
        """제임스 디렉터의 자기 소개 레포지토리 구현 메소드"""

        response: JamesDirectorResponse = JamesDirectorResponse(
            id=query.id * 10000, name=query.name + "이 레포지토리에 다녀옴"
        )
        return response

    async def upload_titanic_file(
        self,
        person_commands: list[PersonCommand],
        booking_commands: list[BookingCommand],
        filename: str,
    ) -> int:
        if AsyncSessionLocal is None:
            raise HTTPException(
                status_code=503,
                detail="DATABASE_URL이 .env 등에 설정되지 않았습니다.",
            )

        await _ensure_james_director_tables()

        if self._session is None:
            async with AsyncSessionLocal() as session:
                await self._save_person_and_booking_commands(
                    session=session,
                    person_commands=person_commands,
                    booking_commands=booking_commands,
                )
                await session.commit()
        else:
            await self._save_person_and_booking_commands(
                session=self._session,
                person_commands=person_commands,
                booking_commands=booking_commands,
            )
            await self._session.commit()

        return len(person_commands)

    async def _save_person_and_booking_commands(
        self,
        *,
        session: AsyncSession,
        person_commands: list[PersonCommand],
        booking_commands: list[BookingCommand],
    ) -> int:
        pairs: list[tuple[str, dict[str, object], dict[str, object]]] = []
        for person_cmd, booking_cmd in zip(
            person_commands, booking_commands, strict=False
        ):
            passenger_id = (person_cmd.passenger_id or "").strip()
            if not passenger_id:
                continue
            pairs.append(
                (
                    passenger_id,
                    _person_fields(person_cmd, passenger_id),
                    _booking_fields(booking_cmd),
                )
            )

        if not pairs:
            return 0

        person_values = [person_data for _, person_data, _ in pairs]
        for chunk_start in range(0, len(person_values), _BULK_CHUNK_SIZE):
            chunk = person_values[chunk_start : chunk_start + _BULK_CHUNK_SIZE]
            person_insert = pg_insert(JackTrainerOrm).values(chunk)
            await session.execute(
                person_insert.on_conflict_do_update(
                    index_elements=[JackTrainerOrm.passenger_id],
                    set_={
                        "name": person_insert.excluded.name,
                        "gender": person_insert.excluded.gender,
                        "age": person_insert.excluded.age,
                        "sib_sp": person_insert.excluded.sib_sp,
                        "parch": person_insert.excluded.parch,
                        "survived": person_insert.excluded.survived,
                    },
                )
            )

        booking_values: list[dict[str, object]] = []
        for passenger_id, _, booking_data in pairs:
            booking_values.append({"passenger_id": passenger_id, **booking_data})

        for chunk_start in range(0, len(booking_values), _BULK_CHUNK_SIZE):
            chunk = booking_values[chunk_start : chunk_start + _BULK_CHUNK_SIZE]
            booking_insert = pg_insert(RoseModelOrm).values(chunk)
            await session.execute(
                booking_insert.on_conflict_do_update(
                    index_elements=[RoseModelOrm.passenger_id],
                    set_={
                        "pclass": booking_insert.excluded.pclass,
                        "ticket": booking_insert.excluded.ticket,
                        "fare": booking_insert.excluded.fare,
                        "cabin": booking_insert.excluded.cabin,
                        "embarked": booking_insert.excluded.embarked,
                    },
                )
            )

        return len(pairs)
