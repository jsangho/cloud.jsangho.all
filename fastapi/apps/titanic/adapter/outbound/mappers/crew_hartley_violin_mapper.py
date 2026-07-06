"""crew_hartley_violin 슬라이스 Mapper — Entity ↔ HartleyViolinOrm (기획 홀딩)."""

from __future__ import annotations

from titanic.adapter.outbound.orm.crew_hartley_violin_orm import HartleyViolinOrm


class HartleyViolinMapper:
    """ORM·Entity 연결. Entity/ORM 테이블 정의 후 to_entity·to_orm 구현."""

    orm_class = HartleyViolinOrm
