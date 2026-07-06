from __future__ import annotations

from datetime import datetime

from core.matrix.grid_oracle_database_manager import Base
from core.matrix.vault_keymaker_secret_manager import EMBEDDING_DIM
from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Float, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column


class ReceiverOrm(Base):
    __tablename__ = "receiver_emails"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    from_email: Mapped[str] = mapped_column(String(255))
    from_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    to_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(500), nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    message_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, unique=True, index=True
    )
    receiver_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    is_read: Mapped[bool] = mapped_column(default=False)
    spam_label: Mapped[str] = mapped_column(String(32), server_default="ham")
    spam_confidence: Mapped[float] = mapped_column(Float, server_default="1.0")
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM))
