from __future__ import annotations

from core.matrix.grid_oracle_database_manager import Base
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column


class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    login_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    nickname: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False, default="user")

    def to_log_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "login_id": self.login_id,
            "nickname": self.nickname,
            "email": self.email,
            "role": self.role,
        }
