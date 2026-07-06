from __future__ import annotations

from dataclasses import dataclass

from titanic.domain.value_objects.age_vo import Age
from titanic.domain.value_objects.family_relation_vo import FamilyRelation
from titanic.domain.value_objects.gender_vo import Gender
from titanic.domain.value_objects.survived_vo import Survived


@dataclass
class PassengerEntity:
    id: int
    passenger_id: str | None
    name: str | None
    gender: Gender
    age: Age
    family_relation: FamilyRelation
    survival_status: Survived

    def is_high_risk(self) -> bool:
        if self.gender.is_female():
            return False
        if self.age.value is None or self.age.value < 18:
            return False
        if not self.family_relation.is_alone:
            return False
        return True

    def has_family(self) -> bool:
        return not self.family_relation.is_alone

    def record_survival(self, survived: bool) -> None:
        self.survival_status = Survived(survived=survived)

    @classmethod
    def from_orm(cls, orm) -> PassengerEntity:
        return cls(
            id=orm.id,
            passenger_id=orm.passenger_id,
            name=orm.name,
            gender=Gender.from_raw(orm.gender),
            age=Age.from_raw(orm.age),
            family_relation=FamilyRelation.from_raw(orm.sib_sp, orm.parch),
            survival_status=Survived.from_raw(orm.survived),
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PassengerEntity):
            return False
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)
