from __future__ import annotations

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from core.matrix.grid_oracle_database_manager import Base
from core.matrix.vault_keymaker_secret_manager import EMBEDDING_DIM


class ScheduleOrm(Base):
    """경기 일정.

    ERD 원본은 sche_date를 PK로 표기하지만, 프로젝트 표준(ENTITY_RULE.md)에 따라
    surrogate id를 PK로 사용한다. 같은 날짜에 여러 경기가 존재할 수 있어
    sche_date에는 unique 제약을 두지 않고 인덱스만 부여한다(사용자 확인 사항).
    """

    __tablename__ = "schedule"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sche_date: Mapped[str | None] = mapped_column(String(10), index=True, nullable=True)
    stadium_id: Mapped[str | None] = mapped_column(
        String(10), ForeignKey("stadium.stadium_id"), nullable=True
    )
    gubun: Mapped[str | None] = mapped_column(String(10), nullable=True)
    hometeam_id: Mapped[str | None] = mapped_column(String(10), nullable=True)
    awayteam_id: Mapped[str | None] = mapped_column(String(10), nullable=True)
    home_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(EMBEDDING_DIM), nullable=True
    )
