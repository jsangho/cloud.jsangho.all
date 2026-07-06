"""crew_andrews_architect 슬라이스 Mapper — Entity ↔ AndrewsArchitectOrm (기획 홀딩)."""

from __future__ import annotations

from titanic.adapter.outbound.orm.crew_andrews_architect_orm import AndrewsArchitectOrm


class AndrewsArchitectMapper:
    """ORM·Entity 연결. Entity/ORM 테이블 정의 후 to_entity·to_orm 구현."""

    orm_class = AndrewsArchitectOrm
