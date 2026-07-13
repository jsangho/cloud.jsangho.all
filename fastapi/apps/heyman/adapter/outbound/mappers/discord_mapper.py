"""discord 슬라이스 Mapper — Entity ↔ DiscordMessageOrm."""

from __future__ import annotations

from heyman.adapter.outbound.orm.discord_orm import DiscordMessageOrm


class DiscordMapper:
    """ORM·Entity 연결. Entity/ORM 테이블 정의 후 to_entity·to_orm 구현."""

    orm_class = DiscordMessageOrm
