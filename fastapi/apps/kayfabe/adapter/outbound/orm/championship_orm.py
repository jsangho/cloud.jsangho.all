from __future__ import annotations

from core.matrix.grid_oracle_database_manager import Base
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column


class ChampionshipTitleModel(Base):
    """현역 WWE 챔피언십 타이틀 (NeonDB, 카탈로그 동기화)."""

    __tablename__ = "championship_titles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    brand_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    belt_name: Mapped[str] = mapped_column(String(200), nullable=False)
    champions_json: Mapped[str] = mapped_column(String(500), nullable=False)
    team_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    won_at: Mapped[str] = mapped_column(String(200), nullable=False)
    won_event: Mapped[str | None] = mapped_column(String(200), nullable=True)
    tier: Mapped[str] = mapped_column(String(20), nullable=False)
    as_of: Mapped[str] = mapped_column(String(20), nullable=False)
