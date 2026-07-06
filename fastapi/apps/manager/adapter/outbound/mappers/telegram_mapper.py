"""telegram 슬라이스 Mapper — Entity ↔ TelegramMessageOrm."""

from __future__ import annotations

from manager.adapter.outbound.orm.telegram_orm import TelegramMessageOrm


class TelegramMapper:
    """ORM·Entity 연결. Entity/ORM 테이블 정의 후 to_entity·to_orm 구현."""

    orm_class = TelegramMessageOrm
