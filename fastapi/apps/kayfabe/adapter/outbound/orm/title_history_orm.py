from __future__ import annotations

from datetime import datetime

from core.matrix.grid_oracle_database_manager import Base
from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column


class TitleAcquisitionModel(Base):
    """선수/팀의 챔피언십 벨트 획득 이력 (NeonDB, PLE 경기 결과 기반)."""

    __tablename__ = "title_acquisitions"
    __table_args__ = (
        UniqueConstraint(
            "match_id",
            "competitor_name",
            name="uq_title_acq_match_comp",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    competitor_name: Mapped[str] = mapped_column(
        String(200), nullable=False, index=True
    )
    belt_name: Mapped[str] = mapped_column(String(200), nullable=False)
    won_at: Mapped[str] = mapped_column(String(200), nullable=False)
    won_at_slug: Mapped[str | None] = mapped_column(String(64), nullable=True)
    match_key: Mapped[str | None] = mapped_column(String(80), nullable=True)
    match_id: Mapped[int | None] = mapped_column(
        ForeignKey("ple_matches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="match")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
