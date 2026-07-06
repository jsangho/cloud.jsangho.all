from __future__ import annotations

from typing import Any

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from titanic.adapter.outbound.orm.passenger_jack_trainer_orm import JackTrainerOrm
from titanic.adapter.outbound.orm.passenger_rose_model_strategies import RoseModelOrm
from titanic.app.dtos.crew_walter_roaster_dto import (
    WalterRoasterQuery,
    WalterRoasterResponse,
)
from titanic.app.ports.output.crew_walter_roaster_port import WalterRoasterPort


def _to_row(person: JackTrainerOrm, booking: RoseModelOrm) -> dict[str, Any]:
    return {
        "passenger_id": person.passenger_id,
        "name": person.name,
        "survived": person.survived,
        "pclass": booking.pclass,
        "gender": person.gender,
        "age": person.age,
        "sibsp": person.sib_sp,
        "parch": person.parch,
        "fare": booking.fare,
        "cabin": booking.cabin,
        "embarked": booking.embarked,
    }


class WalterRoasterRepository(WalterRoasterPort):
    """승객 명단 관리 저장소"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_train_set(self) -> pd.DataFrame:
        """Survived 컬럼이 있는 데이터 전체를 데이터프레임으로 반환하는 메소드"""
        result = await self.session.execute(
            select(JackTrainerOrm, RoseModelOrm)
            .join(
                RoseModelOrm, RoseModelOrm.passenger_id == JackTrainerOrm.passenger_id
            )
            .where(JackTrainerOrm.survived.isnot(None))
            .order_by(JackTrainerOrm.passenger_id.asc())
        )
        rows = result.all()
        return pd.DataFrame([_to_row(p, b) for p, b in rows])

    async def get_test_set(self) -> pd.DataFrame:
        """Survived 컬럼이 없는 데이터 전체를 데이터프레임으로 반환하는 메소드"""
        result = await self.session.execute(
            select(JackTrainerOrm, RoseModelOrm)
            .join(
                RoseModelOrm, RoseModelOrm.passenger_id == JackTrainerOrm.passenger_id
            )
            .where(JackTrainerOrm.survived.is_(None))
            .order_by(JackTrainerOrm.passenger_id.asc())
        )
        rows = result.all()
        df = pd.DataFrame([_to_row(p, b) for p, b in rows])
        return df.drop(columns=["survived"], errors="ignore")

    async def introduce_myself(
        self, query: WalterRoasterQuery
    ) -> WalterRoasterResponse:
        return WalterRoasterResponse(
            id=query.id * 10000,
            name=query.name + "가 레포지토리에 다녀옴",
        )

    async def list_openfile_page(self, *, page: int, page_size: int) -> dict[str, Any]:
        safe_page_size = max(1, min(int(page_size), 200))
        safe_page = max(1, int(page))
        offset = (safe_page - 1) * safe_page_size

        count_result = await self.session.execute(
            select(func.count()).select_from(JackTrainerOrm)
        )
        total = int(count_result.scalar_one())

        result = await self.session.execute(
            select(JackTrainerOrm, RoseModelOrm)
            .join(
                RoseModelOrm, RoseModelOrm.passenger_id == JackTrainerOrm.passenger_id
            )
            .order_by(JackTrainerOrm.passenger_id.asc())
            .offset(offset)
            .limit(safe_page_size)
        )
        rows = result.all()

        items = [
            {
                "PassengerId": person.passenger_id,
                "Survived": person.survived,
                "Pclass": booking.pclass,
                "Name": person.name,
                "gender": person.gender,
                "Age": person.age,
                "SibSp": person.sib_sp,
                "Parch": person.parch,
                "Ticket": booking.ticket,
                "Fare": booking.fare,
                "Cabin": booking.cabin,
                "Embarked": booking.embarked,
            }
            for person, booking in rows
        ]

        return {
            "page": safe_page,
            "pageSize": safe_page_size,
            "total": total,
            "items": items,
        }
