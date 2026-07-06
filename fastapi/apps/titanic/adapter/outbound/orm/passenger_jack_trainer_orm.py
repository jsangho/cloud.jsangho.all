"""passenger_jack_trainer 슬라이스 ORM."""

from __future__ import annotations

from core.matrix.grid_oracle_database_manager import Base
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column


class JackTrainerOrm(Base):
    __tablename__ = "passengers"

    passenger_id: Mapped[str | None] = mapped_column(
        String, primary_key=True, nullable=True
    )
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    gender: Mapped[str | None] = mapped_column(String, nullable=True)
    age: Mapped[str | None] = mapped_column(String, nullable=True)
    sib_sp: Mapped[str | None] = mapped_column(String, nullable=True)
    parch: Mapped[str | None] = mapped_column(String, nullable=True)
    survived: Mapped[str | None] = mapped_column(String, nullable=True)
