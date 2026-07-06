from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Booking:
    """RoseModel 슬라이스 예약(Booking) Entity."""

    id: int
    person_id: str | None = None
    pclass: str | None = None
    ticket: str | None = None
    fare: str | None = None
    cabin: str | None = None
    embarked: str | None = None

    @classmethod
    def create(
        cls,
        *,
        id: int,
        person_id: str | None = None,
        pclass: str | None = None,
        ticket: str | None = None,
        fare: str | None = None,
        cabin: str | None = None,
        embarked: str | None = None,
    ) -> Booking:
        return cls(
            id=id,
            person_id=person_id,
            pclass=pclass,
            ticket=ticket,
            fare=fare,
            cabin=cabin,
            embarked=embarked,
        )
