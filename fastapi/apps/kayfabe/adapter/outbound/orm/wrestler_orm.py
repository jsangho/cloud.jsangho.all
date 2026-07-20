from __future__ import annotations

from core.matrix.grid_oracle_database_manager import Base
from core.matrix.vault_keymaker_secret_manager import EMBEDDING_DIM
from pgvector.sqlalchemy import Vector
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column


class WrestlerOrm(Base):
    __tablename__ = "wrestlers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(150))
    real_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    ring_names: Mapped[str | None] = mapped_column(Text, nullable=True)
    stable_team: Mapped[str | None] = mapped_column(String(100), nullable=True)
    height: Mapped[str | None] = mapped_column(String(255), nullable=True)
    weight: Mapped[str | None] = mapped_column(String(255), nullable=True)
    birth_date: Mapped[str | None] = mapped_column(String(50), nullable=True)
    birth_place: Mapped[str | None] = mapped_column(String(150), nullable=True)
    billed_from: Mapped[str | None] = mapped_column(String(150), nullable=True)
    trainer: Mapped[str | None] = mapped_column(Text, nullable=True)
    finisher: Mapped[str | None] = mapped_column(Text, nullable=True)
    brand: Mapped[str | None] = mapped_column(String(20), nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(EMBEDDING_DIM), nullable=True
    )
