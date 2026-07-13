from __future__ import annotations

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from core.matrix.grid_oracle_database_manager import Base


class StadiumOrm(Base):
    """경기장. ERD 원본 오탈자 `statdium_name`을 그대로 유지한다."""

    __tablename__ = "stadium"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    stadium_id: Mapped[str] = mapped_column(
        String(10), unique=True, index=True, nullable=False
    )
    statdium_name: Mapped[str | None] = mapped_column(String(40), nullable=True)
    hometeam_id: Mapped[str | None] = mapped_column(String(10), nullable=True)
    seat_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    address: Mapped[str | None] = mapped_column(String(60), nullable=True)
    ddd: Mapped[str | None] = mapped_column(String(10), nullable=True)
    tel: Mapped[str | None] = mapped_column(String(10), nullable=True)
