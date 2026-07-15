from __future__ import annotations

from core.matrix.grid_oracle_database_manager import Base
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column


class DiscordMessageOrm(Base):
    __tablename__ = "discord_messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    channel_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str | None] = mapped_column(String(32), nullable=True)
