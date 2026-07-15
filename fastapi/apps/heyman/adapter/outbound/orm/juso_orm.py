from __future__ import annotations

from core.matrix.grid_oracle_database_manager import Base
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column


class JusoContactOrm(Base):
    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255))
    given_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    family_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    nickname: Mapped[str | None] = mapped_column(String(128), nullable=True)
    birthday: Mapped[str | None] = mapped_column(String(32), nullable=True)
    gender: Mapped[str | None] = mapped_column(String(32), nullable=True)
    occupation: Mapped[str | None] = mapped_column(String(128), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    group_membership: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email_1_value: Mapped[str | None] = mapped_column(
        String(255), nullable=True, unique=True, index=True
    )
    email_2_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone_1_value: Mapped[str | None] = mapped_column(String(64), nullable=True)
    phone_2_value: Mapped[str | None] = mapped_column(String(64), nullable=True)
    address_1_formatted: Mapped[str | None] = mapped_column(Text, nullable=True)
    address_1_street: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address_1_city: Mapped[str | None] = mapped_column(String(128), nullable=True)
    address_1_region: Mapped[str | None] = mapped_column(String(128), nullable=True)
    address_1_postal_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    address_1_country: Mapped[str | None] = mapped_column(String(128), nullable=True)
    org_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    org_title: Mapped[str | None] = mapped_column(String(128), nullable=True)
    org_department: Mapped[str | None] = mapped_column(String(128), nullable=True)
    website_1_value: Mapped[str | None] = mapped_column(String(512), nullable=True)
