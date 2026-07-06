"""email 슬라이스 Mapper — gateway 패턴 사용, ORM 매핑 없음."""

from __future__ import annotations

from manager.adapter.outbound.orm.email_orm import EmailOrm


class EmailMapper:
    """ORM·Entity 연결. Entity/ORM 테이블 정의 후 to_entity·to_orm 구현."""

    orm_class = EmailOrm
