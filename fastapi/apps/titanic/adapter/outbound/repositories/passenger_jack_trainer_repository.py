from __future__ import annotations

from typing import Any

from numpy import select
from sqlalchemy.ext.asyncio import AsyncSession

from titanic.adapter.outbound.orm.passenger_jack_trainer_orm import JackTrainerOrm
from titanic.adapter.outbound.orm.passenger_rose_model_strategies import RoseModelOrm
from titanic.app.dtos.passenger_jack_trainer_dto import (
    JackTrainerQuery,
    JackTrainerResponse,
)
from titanic.app.ports.output.passenger_jack_trainer_port import JackTrainerPort


class JackTrainerRepository(JackTrainerPort):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def introduce_myself(self, query: JackTrainerQuery) -> JackTrainerResponse:
        return JackTrainerResponse(
            id=query.id * 10000,
            name=query.name + "이 레포지토리에 다녀옴",
        )

    async def get_training_data(self) -> list[dict[str, Any]]:
        """생존 예측 모델 학습에 사용할 피처 데이터 조회"""
        rows = (
            await self.session.execute(
                select(JackTrainerOrm, RoseModelOrm)
                .outerjoin(RoseModelOrm, RoseModelOrm.person_id == JackTrainerOrm.id)
                .order_by(JackTrainerOrm.id)
            )
        ).all()
        return [
            {
                "pclass": booking.pclass if booking else None,
                "gender": person.gender,
                "age": person.age,
                "sibsp": person.sib_sp,
                "parch": person.parch,
                "fare": booking.fare if booking else None,
                "survived": person.survived,
            }
            for person, booking in rows
        ]
