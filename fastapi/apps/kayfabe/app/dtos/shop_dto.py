from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ShopItemResponse:
    code: str
    name: str
    description: str
    price: int
    category: str
    is_consumable: bool


@dataclass(frozen=True)
class WalletResponse:
    """`earned`는 적중 예측 × 배점 집계, `spent`는 원장이 깎아낸 총액."""

    earned: int
    spent: int
    balance: int


@dataclass(frozen=True)
class InventoryItemResponse:
    id: int
    item_code: str
    item_name: str
    category: str
    context_key: str
    is_equipped: bool
    acquired_at: datetime


@dataclass(frozen=True)
class PurchaseCommand:
    user_id: int
    item_code: str
    context_key: str = ""


@dataclass(frozen=True)
class PurchaseReceipt:
    inventory_id: int
    item_code: str
    price: int
    balance_after: int
