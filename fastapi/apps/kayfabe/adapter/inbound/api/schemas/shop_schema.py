from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "ShopItemSchema",
    "WalletSchema",
    "InventoryItemSchema",
    "PurchaseRequestSchema",
    "PurchaseReceiptSchema",
    "EquipRequestSchema",
]


class ShopItemSchema(BaseModel):
    code: str
    name: str
    description: str
    price: int
    category: str
    is_consumable: bool = Field(..., alias="isConsumable")

    model_config = ConfigDict(populate_by_name=True)


class WalletSchema(BaseModel):
    earned: int = Field(..., description="적중 예측 × 배점 합계")
    spent: int = Field(..., description="원장이 깎아낸 총액 (환급은 상쇄)")
    balance: int = Field(..., description="earned - spent")

    model_config = ConfigDict(populate_by_name=True)


class InventoryItemSchema(BaseModel):
    id: int
    item_code: str = Field(..., alias="itemCode")
    item_name: str = Field(..., alias="itemName")
    category: str
    context_key: str = Field(..., alias="contextKey")
    is_equipped: bool = Field(..., alias="isEquipped")
    acquired_at: datetime = Field(..., alias="acquiredAt")

    model_config = ConfigDict(populate_by_name=True)


class PurchaseRequestSchema(BaseModel):
    """구매 요청.

    `userId`를 받지 않는다 — 사용자 식별은 토큰에서만 얻는다.
    가격도 받지 않는다 — 서버의 상품 행이 유일한 출처다.
    """

    item_code: str = Field(..., alias="itemCode", min_length=1, max_length=64)
    context_key: str = Field(default="", alias="contextKey", max_length=64)

    model_config = ConfigDict(populate_by_name=True)


class PurchaseReceiptSchema(BaseModel):
    inventory_id: int = Field(..., alias="inventoryId")
    item_code: str = Field(..., alias="itemCode")
    price: int
    balance_after: int = Field(..., alias="balanceAfter")

    model_config = ConfigDict(populate_by_name=True)


class EquipRequestSchema(BaseModel):
    is_equipped: bool = Field(..., alias="isEquipped")

    model_config = ConfigDict(populate_by_name=True)
