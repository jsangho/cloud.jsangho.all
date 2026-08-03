from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from core.matrix.grid_oracle_database_manager import Base
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column


class ShopItemCategory(StrEnum):
    """`shop_items.category`에 들어가는 값. 컬럼은 문자열이고 이건 호출부용 상수다."""

    TITLE = "title"
    NICKNAME_COLOR = "nickname_color"
    BADGE = "badge"
    REPORT = "report"
    HOF = "hof"


# 순위표가 한 자리에 하나씩만 그리는 카테고리 — 칭호는 닉네임 앞, 색상은 닉네임 자체,
# 뱃지는 닉네임 뒤. 자리가 하나뿐이라 장착도 카테고리당 하나로 제한한다
# (`ShopPgRepository.set_equipped`). 소모성 리포트·명예의 전당은 순위표에 자리가
# 없으므로 이 규칙을 적용하지 않는다.
COSMETIC_CATEGORIES = (
    ShopItemCategory.TITLE,
    ShopItemCategory.NICKNAME_COLOR,
    ShopItemCategory.BADGE,
)


class PointLedgerEntryType(StrEnum):
    """`point_ledger_entries.entry_type`에 들어가는 값."""

    PURCHASE = "purchase"
    REFUND = "refund"
    ADMIN_GRANT = "admin_grant"
    RECONCILE = "reconcile"


class ShopItemModel(Base):
    """상점 상품 카탈로그 — `_docs/shop-point-ledger.md` §3-1."""

    __tablename__ = "shop_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(
        String(80), nullable=False, unique=True, index=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    price: Mapped[int] = mapped_column(Integer, nullable=False)
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    is_consumable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class PointLedgerEntryModel(Base):
    """포인트 원장 — 지출·환급·보정. 추가 전용(append-only) — `§3-2`."""

    __tablename__ = "point_ledger_entries"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    entry_type: Mapped[str] = mapped_column(String(20), nullable=False)
    shop_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("shop_items.id", ondelete="SET NULL"), nullable=True
    )
    memo: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class UserShopItemModel(Base):
    """사용자 보유·장착 상태 — `§3-3`."""

    __tablename__ = "user_shop_items"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "shop_item_id", "context_key", name="uq_user_shop_item_context"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    shop_item_id: Mapped[int] = mapped_column(
        ForeignKey("shop_items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    context_key: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    is_equipped: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    acquired_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
