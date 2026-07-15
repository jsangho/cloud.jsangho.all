from __future__ import annotations

from core.matrix.grid_oracle_database_manager import Base
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column


class EmailOrm(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    to_email: Mapped[str] = mapped_column(String(255), index=True)
    subject: Mapped[str | None] = mapped_column(String(512), nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str | None] = mapped_column(String(32), nullable=True)
