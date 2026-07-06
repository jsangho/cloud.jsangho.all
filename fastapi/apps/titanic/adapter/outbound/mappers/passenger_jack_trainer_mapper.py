"""passenger_jack_trainer 슬라이스 Mapper — PassengerEntity ↔ JackTrainerOrm."""

from __future__ import annotations

from titanic.adapter.outbound.orm.passenger_jack_trainer_orm import JackTrainerOrm
from titanic.domain.entities.passenger_jack_trainer_entity import PassengerEntity


class JackTrainerMapper:
    @staticmethod
    def to_entity(orm) -> PassengerEntity:
        return PassengerEntity.from_orm(orm)

    @staticmethod
    def to_orm(entity: PassengerEntity) -> JackTrainerOrm:
        survived: str | None = None
        if not entity.survival_status.is_unknown:
            survived = "1" if entity.survival_status.survived else "0"

        return JackTrainerOrm(
            id=entity.id,
            passenger_id=entity.passenger_id,
            name=entity.name,
            gender=str(entity.gender),
            age=str(entity.age) if not entity.age.is_unknown else None,
            sib_sp=str(entity.family_relation.sib_sp),
            parch=str(entity.family_relation.parch),
            survived=survived,
        )
