from kayfabe.adapter.inbound.api.schemas.shop_schema import (
    InventoryItemSchema,
    PurchaseReceiptSchema,
    ShopItemSchema,
    WalletSchema,
)
from kayfabe.app.dtos.shop_dto import (
    InventoryItemResponse,
    PurchaseReceipt,
    ShopItemResponse,
    WalletResponse,
)


def shop_item_to_schema(dto: ShopItemResponse) -> ShopItemSchema:
    return ShopItemSchema(
        code=dto.code,
        name=dto.name,
        description=dto.description,
        price=dto.price,
        category=dto.category,
        is_consumable=dto.is_consumable,
    )


def wallet_to_schema(dto: WalletResponse) -> WalletSchema:
    return WalletSchema(earned=dto.earned, spent=dto.spent, balance=dto.balance)


def inventory_item_to_schema(dto: InventoryItemResponse) -> InventoryItemSchema:
    return InventoryItemSchema(
        id=dto.id,
        item_code=dto.item_code,
        item_name=dto.item_name,
        category=dto.category,
        context_key=dto.context_key,
        is_equipped=dto.is_equipped,
        acquired_at=dto.acquired_at,
    )


def purchase_receipt_to_schema(dto: PurchaseReceipt) -> PurchaseReceiptSchema:
    return PurchaseReceiptSchema(
        inventory_id=dto.inventory_id,
        item_code=dto.item_code,
        price=dto.price,
        balance_after=dto.balance_after,
    )
