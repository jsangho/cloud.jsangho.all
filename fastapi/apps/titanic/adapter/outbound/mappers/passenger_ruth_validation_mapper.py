"""passenger_ruth_validation 슬라이스 Mapper — Entity ↔ RuthValidationOrm (기획 홀딩)."""

from __future__ import annotations

from titanic.adapter.outbound.orm.passenger_ruth_validation_orm import RuthValidationOrm


class RuthValidationMapper:
    """ORM·Entity 연결. Entity/ORM 테이블 정의 후 to_entity·to_orm 구현."""

    orm_class = RuthValidationOrm
