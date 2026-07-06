"""passenger_cal_tester 슬라이스 Mapper — Entity ↔ CalTesterOrm (기획 홀딩)."""

from __future__ import annotations

from titanic.adapter.outbound.orm.passenger_cal_tester_orm import CalTesterOrm


class CalTesterMapper:
    """ORM·Entity 연결. Entity/ORM 테이블 정의 후 to_entity·to_orm 구현."""

    orm_class = CalTesterOrm
