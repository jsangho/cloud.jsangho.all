"""crew_james_director 슬라이스 Mapper — Entity ↔ JamesDirectorOrm (기획 홀딩)."""

from __future__ import annotations

from titanic.adapter.outbound.orm.crew_james_director_orm import JamesDirectorOrm


class JamesDirectorMapper:
    """ORM·Entity 연결. Entity/ORM 테이블 정의 후 to_entity·to_orm 구현."""

    orm_class = JamesDirectorOrm
