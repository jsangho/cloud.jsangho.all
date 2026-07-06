"""passenger_isidor_couple 슬라이스 Mapper — Entity ↔ IsidorCoupleOrm (기획 홀딩)."""

from __future__ import annotations

from titanic.adapter.outbound.orm.passenger_isidor_couple_orm import IsidorCoupleOrm


class IsidorCoupleMapper:
    """ORM·Entity 연결. Entity/ORM 테이블 정의 후 to_entity·to_orm 구현."""

    orm_class = IsidorCoupleOrm
